"""Screens an application's form against its own standard and the network triggers."""

from decimal import Decimal

import pandas as pd

from config import config
from data_pipeline.common_cleaning import convert_power_to_amps_per_phase


def _is_blank(value):
    if value is None or value is pd.NA:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _answer(application, column_name):
    """The form's answer, or None when blank."""
    value = application.get(column_name)
    return None if _is_blank(value) else value


def _decimal(value):
    """An answer as an exact decimal, read from its shortest written form."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return Decimal(value)
    return Decimal(repr(float(value))) if not isinstance(value, str) else Decimal(value)


def find_network_triggers(application):
    """Name every network trigger of the Low-Carbon Connections Policy the application meets."""
    technology = _answer(application, config.TECHNOLOGY_COLUMN)
    if technology not in config.CONNECTION_STANDARD_DOCUMENTS:
        raise ValueError(
            config.UNKNOWN_TECHNOLOGY_MESSAGE.format(
                application_reference=application.get(config.APPLICATION_REFERENCE_COLUMN),
                technology=technology,
            )
        )
    triggers = []

    looped = _answer(application, config.LOOPED_SERVICE_COLUMN)
    if looped is None or looped == config.BOOLEAN_YES:
        triggers.append(config.LOOPED_SERVICE_TRIGGER)

    if _supply_capacity_reached(application):
        triggers.append(config.SUPPLY_CAPACITY_TRIGGER)

    if technology in config.GENERATING_TECHNOLOGIES and _generation_above_notify_limit(
        application
    ):
        triggers.append(config.GENERATION_TRIGGER)
    return triggers


def _demand_that_counts(application):
    """The demand the supply capacity trigger is judged on, or None when blank."""
    limiter = _answer(application, config.LOAD_LIMITER_FITTED_COLUMN)
    demand = _answer(application, config.MAXIMUM_DEMAND_COLUMN)
    setting = _answer(application, config.LOAD_LIMITER_SETTING_COLUMN)
    if limiter == config.BOOLEAN_YES:
        return None if setting is None else _decimal(setting)
    if limiter == config.BOOLEAN_NO:
        return None if demand is None else _decimal(demand)
    if demand is None or setting is None:
        return None if demand is None else _decimal(demand)
    return max(_decimal(demand), _decimal(setting))


def _supply_capacity_reached(application):
    cut_out = _answer(application, config.CUT_OUT_RATING_COLUMN)
    demand = _demand_that_counts(application)
    if cut_out is None or demand is None:
        return True
    return demand >= _decimal(cut_out) or demand > config.SUPPLY_MAXIMUM_AMPS


def _generation_above_notify_limit(application):
    inverter = _answer(application, config.INVERTER_CAPACITY_COLUMN)
    existing = _answer(application, config.EXISTING_GENERATION_COLUMN)
    phases = _answer(application, config.EQUIPMENT_PHASES_COLUMN)
    if inverter is None or existing is None or phases is None:
        return True
    capacity_amps = convert_power_to_amps_per_phase(
        _decimal(inverter) + _decimal(existing), int(phases)
    )
    if capacity_amps <= config.NOTIFY_GENERATION_AMPS:
        return False
    fitted = _answer(application, config.EXPORT_LIMITATION_FITTED_COLUMN)
    certified = _answer(application, config.EXPORT_SCHEME_CERTIFIED_COLUMN)
    export_limit = _answer(application, config.EXPORT_LIMIT_COLUMN)
    if (
        fitted == config.BOOLEAN_YES
        and certified == config.BOOLEAN_YES
        and export_limit is not None
        and capacity_amps <= config.FAST_TRACK_GENERATION_AMPS
    ):
        export_amps = convert_power_to_amps_per_phase(_decimal(export_limit), int(phases))
        if export_amps <= config.NOTIFY_GENERATION_AMPS:
            return False
    return True


def _judge_yes_or_no(application, column_name):
    answer = _answer(application, column_name)
    if answer is None:
        return config.REQUIREMENT_NOT_DOCUMENTED, [column_name]
    if answer == config.BOOLEAN_YES:
        return config.REQUIREMENT_MET, []
    return config.REQUIREMENT_NOT_MET, []


def _judge_maximum(application, column_name, maximum):
    answer = _answer(application, column_name)
    if answer is None:
        return config.REQUIREMENT_NOT_DOCUMENTED, [column_name]
    if _decimal(answer) <= maximum:
        return config.REQUIREMENT_MET, []
    return config.REQUIREMENT_NOT_MET, []


def _judge_power_factor(application, minimum):
    answer = _answer(application, config.POWER_FACTOR_COLUMN)
    if answer is None:
        return config.REQUIREMENT_NOT_DOCUMENTED, [config.POWER_FACTOR_COLUMN]
    if _decimal(answer) >= minimum:
        return config.REQUIREMENT_MET, []
    return config.REQUIREMENT_NOT_MET, []


def _judge_earthing(application, maximum_ohms):
    arrangement = _answer(application, config.EARTHING_ARRANGEMENT_COLUMN)
    if arrangement is None:
        return config.REQUIREMENT_NOT_DOCUMENTED, [config.EARTHING_ARRANGEMENT_COLUMN]
    if arrangement == config.EARTHING_TN_S:
        return config.REQUIREMENT_MET, []
    if arrangement == config.EARTHING_TN_C_S:
        return _judge_yes_or_no(application, config.OPEN_PEN_PROTECTION_COLUMN)
    return _judge_maximum(application, config.EARTH_ELECTRODE_COLUMN, maximum_ohms)


def _judge_export_limitation(application, maximum_amps):
    fitted = _answer(application, config.EXPORT_LIMITATION_FITTED_COLUMN)
    if fitted is None:
        return config.REQUIREMENT_NOT_DOCUMENTED, [config.EXPORT_LIMITATION_FITTED_COLUMN]
    if fitted == config.BOOLEAN_NO:
        return config.REQUIREMENT_MET, []
    certified = _answer(application, config.EXPORT_SCHEME_CERTIFIED_COLUMN)
    export_limit = _answer(application, config.EXPORT_LIMIT_COLUMN)
    phases = _answer(application, config.EQUIPMENT_PHASES_COLUMN)
    if certified == config.BOOLEAN_NO:
        return config.REQUIREMENT_NOT_MET, []
    if export_limit is not None and phases is not None:
        export_amps = convert_power_to_amps_per_phase(_decimal(export_limit), int(phases))
        if export_amps > maximum_amps:
            return config.REQUIREMENT_NOT_MET, []
    blanks = []
    if certified is None:
        blanks.append(config.EXPORT_SCHEME_CERTIFIED_COLUMN)
    if export_limit is None:
        blanks.append(config.EXPORT_LIMIT_COLUMN)
    elif phases is None:
        blanks.append(config.EQUIPMENT_PHASES_COLUMN)
    if blanks:
        return config.REQUIREMENT_NOT_DOCUMENTED, blanks
    return config.REQUIREMENT_MET, []


def _judge_requirement(application, requirement, document_name):
    kind = requirement["requirement_kind"]
    rules = requirement.get("rules") or {}
    if kind in config.YES_OR_NO_REQUIREMENT_ANSWERS:
        return _judge_yes_or_no(application, config.YES_OR_NO_REQUIREMENT_ANSWERS[kind])
    if kind in config.CURRENT_REQUIREMENT_ANSWERS:
        return _judge_maximum(
            application,
            config.CURRENT_REQUIREMENT_ANSWERS[kind],
            Decimal(rules[config.MAXIMUM_AMPS_RULE]),
        )
    if kind == config.POWER_FACTOR_REQUIREMENT:
        return _judge_power_factor(
            application, Decimal(rules[config.MINIMUM_POWER_FACTOR_RULE])
        )
    if kind == config.EARTHING_PROTECTION_REQUIREMENT:
        return _judge_earthing(application, Decimal(rules[config.MAXIMUM_OHMS_RULE]))
    if kind == config.EXPORT_LIMITATION_REQUIREMENT:
        return _judge_export_limitation(application, Decimal(rules[config.MAXIMUM_AMPS_RULE]))
    raise ValueError(
        f"{document_name} states a requirement of the kind {kind}, which the screening "
        "does not know"
    )


def screen_application(application, standard):
    """Screen a form against every requirement of its standard and the network triggers."""
    application_reference = application.get(config.APPLICATION_REFERENCE_COLUMN)
    technology = _answer(application, config.TECHNOLOGY_COLUMN)
    if standard.get("technology") != technology:
        raise ValueError(
            config.STANDARD_OF_ANOTHER_TECHNOLOGY_MESSAGE.format(
                application_reference=application_reference,
                technology=technology,
                document_name=standard.get("document_name"),
            )
        )
    document_name = standard.get("document_name")
    requirements = []
    for requirement in standard["requirements"]:
        result, blank_answers = _judge_requirement(application, requirement, document_name)
        requirements.append(
            {
                "requirement_kind": requirement["requirement_kind"],
                "requirement_name": requirement["requirement_name"],
                "requirement_sentence": requirement["requirement_sentence"],
                "rules": dict(requirement.get("rules") or {}),
                "result": result,
                "blank_answers": blank_answers,
            }
        )
    counts = {
        column_name: sum(1 for requirement in requirements if requirement["result"] == result)
        for column_name, result in config.REQUIREMENT_COUNT_RESULTS.items()
    }
    network_triggers = find_network_triggers(application)
    rating_stated = _answer(application, config.RATING_COLUMNS[technology]) is not None
    if counts[config.REQUIREMENTS_MET_COUNT_COLUMN] != len(requirements) or not rating_stated:
        assessment = config.DECISION_RETURN
    elif network_triggers:
        assessment = config.DECISION_REFER
    else:
        assessment = config.DECISION_APPROVE
    screening = {
        "application_reference": application_reference,
        "technology": technology,
        "standard_document": document_name,
        "requirements": requirements,
    }
    screening.update(counts)
    screening.update(
        {
            "network_triggers": network_triggers,
            "rating_stated": rating_stated,
            "assessment": assessment,
            "decisions_open": list(config.DECISIONS_OPEN[assessment]),
        }
    )
    return screening
