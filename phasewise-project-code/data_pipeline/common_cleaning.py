"""Repairs shared by every cleaning run, the live files, the tools and the profiles.

Every function returns a repaired copy and never touches what it was given.
A value in a notation a function does not recognise is refused with a
ValueError naming the column and the values as written.
"""

import html
import re
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

from config import config


def _is_blank(value):
    """True for None, NaN and pandas' NA."""
    if value is None or value is pd.NA:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _refuse_values(column_name, values):
    """Raise the refusal every reader uses, naming the column and the values."""
    written = sorted({str(value) for value in values})
    raise ValueError(
        f"{column_name} holds values in no notation the Connection Rules read: "
        + ", ".join(written)
    )


def _round_half_up(number, step):
    """Round an exact decimal once, half up, to the given step."""
    return Decimal(number).quantize(Decimal(step), rounding=ROUND_HALF_UP)


def remove_duplicate_records(dataframe):
    """Drop rows written twice, keeping the first copy, numbered from nought."""
    return dataframe.drop_duplicates(keep="first").reset_index(drop=True)


def refuse_missing_values(dataframe, required_columns):
    """Refuse a table in which a required key is blank."""
    for column_name in required_columns:
        blank_count = int(dataframe[column_name].isna().sum())
        if blank_count > 0:
            raise ValueError(
                f"{column_name} is blank on {blank_count} rows, and every row must give it"
            )
    return dataframe


def refuse_repeated_references(dataframe, reference_column):
    """Refuse a table in which two rows claim the same identity."""
    repeated = dataframe[reference_column][
        dataframe[reference_column].duplicated(keep=False)
        & dataframe[reference_column].notna()
    ]
    if len(repeated) > 0:
        values = sorted({str(value) for value in repeated})
        raise ValueError(
            f"{reference_column} repeats on more than one row: " + ", ".join(values)
        )
    return dataframe


def remove_rows_missing_target(dataframe, target_column):
    """Keep only the rows that carry an answer, numbered from nought."""
    return dataframe[dataframe[target_column].notna()].reset_index(drop=True)


def normalize_category_values(dataframe, value_mappings):
    """Fold every spelling of a named answer onto its one canonical value."""
    repaired = dataframe.copy()
    for column_name, value_mapping in value_mappings.items():
        if column_name not in repaired.columns:
            continue
        column = repaired[column_name]
        given = column.notna()
        lowered = column[given].astype(str).str.strip().str.lower()
        unknown = column[given][~lowered.isin(value_mapping.keys())]
        if len(unknown) > 0:
            _refuse_values(column_name, unknown)
        mapped = lowered.map(value_mapping)
        result = pd.Series(np.nan, index=column.index, dtype=object)
        result[given] = mapped
        repaired[column_name] = result
    return repaired


def convert_application_references(references):
    """Write every application reference as LCT and seven digits."""
    pattern = re.compile(config.APPLICATION_REFERENCE_PATTERN)
    converted = []
    unreadable = []
    for value in references:
        if _is_blank(value):
            converted.append(np.nan)
            continue
        match = pattern.match(str(value))
        if match is None:
            unreadable.append(value)
            converted.append(np.nan)
            continue
        number = match.group(1)
        converted.append(
            config.APPLICATION_REFERENCE_PREFIX
            + number.zfill(config.APPLICATION_REFERENCE_DIGITS)
        )
    if unreadable:
        _refuse_values(references.name, unreadable)
    return pd.Series(converted, index=references.index, name=references.name, dtype=object)


def refuse_unreadable_identifiers(dataframe, identifier_patterns):
    """Refuse an installer, premises or substation reference in a form no portal uses."""
    for column_name, pattern in identifier_patterns.items():
        if column_name not in dataframe.columns:
            continue
        column = dataframe[column_name]
        given = column[column.notna()].astype(str)
        unreadable = given[~given.str.fullmatch(pattern.strip("^$"))]
        if len(unreadable) > 0:
            _refuse_values(column_name, unreadable)
    return dataframe


def convert_whole_numbers(dataframe, number_patterns):
    """Read counts, cut-out ratings and working days as whole numbers."""
    repaired = dataframe.copy()
    for column_name, pattern in number_patterns.items():
        if column_name not in repaired.columns:
            continue
        compiled = re.compile(pattern)
        numbers = []
        unreadable = []
        for value in repaired[column_name]:
            if _is_blank(value):
                numbers.append(pd.NA)
                continue
            match = compiled.match(str(value))
            if match is None:
                unreadable.append(value)
                numbers.append(pd.NA)
                continue
            numbers.append(int(match.group(1)))
        if unreadable:
            _refuse_values(column_name, unreadable)
        repaired[column_name] = pd.array(numbers, dtype=config.WHOLE_NUMBER_DTYPE)
    return repaired


def convert_phases(dataframe):
    """Read the supply's and the equipment's phases as 1 or 3."""
    repaired = dataframe.copy()
    for column_name in config.PHASE_COLUMNS:
        phases = []
        unreadable = []
        for value in repaired[column_name]:
            if _is_blank(value):
                phases.append(pd.NA)
                continue
            key = str(value).strip().lower()
            if key not in config.PHASE_MAPPING:
                unreadable.append(value)
                phases.append(pd.NA)
                continue
            phases.append(config.PHASE_MAPPING[key])
        if unreadable:
            _refuse_values(column_name, unreadable)
        repaired[column_name] = pd.array(phases, dtype=config.WHOLE_NUMBER_DTYPE)
    return repaired


def treat_impossible_phase_pairs_as_missing(dataframe):
    """Blank the equipment's phases where they exceed the supply's."""
    repaired = dataframe.copy()
    supply = repaired[config.SUPPLY_PHASES_COLUMN]
    equipment = repaired[config.EQUIPMENT_PHASES_COLUMN]
    impossible = (supply.notna() & equipment.notna()).to_numpy(dtype=bool)
    impossible = impossible & (
        equipment.astype("float64").to_numpy() > supply.astype("float64").to_numpy()
    )
    column = repaired[config.EQUIPMENT_PHASES_COLUMN].copy()
    column[impossible] = pd.NA
    repaired[config.EQUIPMENT_PHASES_COLUMN] = column
    return repaired


def convert_power_to_amps_per_phase(kilowatts, phases):
    """Turn a power in kilowatts into amps per phase, exactly, rounded once half up."""
    amps = (
        Decimal(kilowatts)
        * config.WATTS_PER_KILOWATT
        / config.DECLARED_VOLTS
        / Decimal(int(phases))
    )
    return _round_half_up(amps, config.AMPS_STEP)


def _read_current(value, phases):
    """Read one current as an exact decimal of amps per phase, or None when unconvertible.

    Returns (amps, recognised).
    """
    text = str(value)
    amps_match = re.match(config.CURRENT_NOTATIONS[config.AMPS_UNIT], text)
    if amps_match is not None:
        return _round_half_up(Decimal(amps_match.group(1)), config.AMPS_STEP), True
    for notation_name, pattern in config.CURRENT_NOTATIONS.items():
        if notation_name == config.AMPS_UNIT:
            continue
        match = re.match(pattern, text)
        if match is None:
            continue
        number = Decimal(match.group(1).replace(config.THOUSANDS_SEPARATOR, ""))
        kilowatts = number * config.POWER_UNITS[notation_name]
        if _is_blank(phases):
            return None, True
        return convert_power_to_amps_per_phase(kilowatts, int(phases)), True
    return None, False


def convert_currents(dataframe, current_phases):
    """Read every current, in amps or written as a power, as amps per phase."""
    repaired = dataframe.copy()
    for column_name, phases_column in current_phases.items():
        if column_name not in repaired.columns:
            continue
        values = []
        unreadable = []
        for value, phases in zip(repaired[column_name], repaired[phases_column]):
            if _is_blank(value):
                values.append(np.nan)
                continue
            amps, recognised = _read_current(value, phases)
            if not recognised:
                unreadable.append(value)
                values.append(np.nan)
                continue
            values.append(np.nan if amps is None else float(amps))
        if unreadable:
            _refuse_values(column_name, unreadable)
        repaired[column_name] = pd.Series(values, index=repaired.index, dtype="float64")
    return repaired


def _read_amount(value, reading):
    """Read one amount with its reading; None when no notation fits."""
    text = str(value)
    for notation_name, pattern in reading["notations"].items():
        match = re.match(pattern, text)
        if match is None:
            continue
        number = Decimal(match.group(1).replace(config.THOUSANDS_SEPARATOR, ""))
        return _round_half_up(number * reading["units"][notation_name], reading["step"])
    return None


def convert_amounts(dataframe, amount_readings):
    """Read powers, power factors and resistances in every notation a portal writes."""
    repaired = dataframe.copy()
    for column_name, reading in amount_readings.items():
        if column_name not in repaired.columns:
            continue
        values = []
        unreadable = []
        for value in repaired[column_name]:
            if _is_blank(value):
                values.append(np.nan)
                continue
            amount = _read_amount(value, reading)
            if amount is None:
                unreadable.append(value)
                values.append(np.nan)
                continue
            values.append(float(amount))
        if unreadable:
            _refuse_values(column_name, unreadable)
        repaired[column_name] = pd.Series(values, index=repaired.index, dtype="float64")
    return repaired


def treat_values_below_minimum_as_missing(dataframe, minimum_values):
    """Blank readings below the least value that can be true."""
    repaired = dataframe.copy()
    for column_name, minimum in minimum_values.items():
        if column_name not in repaired.columns:
            continue
        column = repaired[column_name].copy()
        below = (column.notna() & (column.astype("float64") < float(minimum))).to_numpy(
            dtype=bool
        )
        column[below] = pd.NA if str(column.dtype) == config.WHOLE_NUMBER_DTYPE else np.nan
        repaired[column_name] = column
    return repaired


def treat_values_above_maximum_as_missing(dataframe, maximum_values):
    """Blank readings above the greatest value that can be true."""
    repaired = dataframe.copy()
    for column_name, maximum in maximum_values.items():
        if column_name not in repaired.columns:
            continue
        column = repaired[column_name].copy()
        above = (column.notna() & (column.astype("float64") > float(maximum))).to_numpy(
            dtype=bool
        )
        column[above] = pd.NA if str(column.dtype) == config.WHOLE_NUMBER_DTYPE else np.nan
        repaired[column_name] = column
    return repaired


def treat_values_outside_sizes_as_missing(dataframe, allowed_sizes):
    """Blank readings that are none of the sizes that exist."""
    repaired = dataframe.copy()
    for column_name, sizes in allowed_sizes.items():
        if column_name not in repaired.columns:
            continue
        column = repaired[column_name].copy()
        given = column.notna().to_numpy(dtype=bool)
        numbers = column.astype("float64").to_numpy()
        outside = given & ~np.isin(numbers, [float(size) for size in sizes])
        column[outside] = pd.NA if str(column.dtype) == config.WHOLE_NUMBER_DTYPE else np.nan
        repaired[column_name] = column
    return repaired


def keep_latest_revision_of_each_application(dataframe):
    """Keep each application once, as its highest revision, in table order."""
    reference_column = config.APPLICATION_REFERENCE_COLUMN
    revision_column = config.REVISION_NUMBER_COLUMN
    references = dataframe[reference_column]
    revisions = dataframe[revision_column]
    blank = (references.isna() | revisions.isna()).to_numpy(dtype=bool)
    if blank.any():
        named = sorted({str(value) for value in references[blank].fillna("(no reference)")})
        raise ValueError(
            "Applications " + ", ".join(named) + f" leave {reference_column} or "
            f"{revision_column} blank, so their latest revision cannot be found"
        )
    repeated = dataframe.duplicated([reference_column, revision_column], keep=False)
    if repeated.any():
        named = sorted({str(value) for value in references[repeated]})
        raise ValueError(
            "Applications " + ", ".join(named) + f" give two rows at the same {revision_column}"
        )
    revision_numbers = revisions.astype("int64")
    latest = revision_numbers.groupby(references).transform("max")
    kept = (revision_numbers == latest).to_numpy(dtype=bool)
    return dataframe[kept].reset_index(drop=True)


def _plain_text(text):
    without_tags = re.sub(config.MARKUP_PATTERN, " ", text)
    unescaped = html.unescape(without_tags)
    return re.sub(config.WHITESPACE_RUN_PATTERN, " ", unescaped).strip()


def convert_markup_to_plain_text(texts):
    """Recover the words a writer meant from text with markup and escaped characters."""
    return texts.map(lambda value: value if _is_blank(value) else _plain_text(str(value)))


def _statement_text(value):
    if _is_blank(value):
        return value
    plain = _plain_text(str(value))
    return plain.lower() if plain.isupper() else plain


def clean_statement_text(texts):
    """Plain words, and a text written wholly in capitals put in small letters."""
    return texts.map(_statement_text)
