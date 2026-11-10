"""The duration model: how many working days a connection will really take."""

from sklearn.ensemble import RandomForestRegressor

from config import config
from data_pipeline.feature_builder import build_model_pipeline
from modeling.model_evaluation import evaluate_regressor


def train_duration_model(train_features, train_target, held_out_features, held_out_target):
    """Fit a random forest on the training logs only.

    A forest's forecast is an average of working days it learned from, so it is
    never below the quickest connection in the training logs.
    """
    estimator = RandomForestRegressor(
        n_estimators=config.DURATION_FOREST_TREES,
        min_samples_leaf=config.DURATION_FOREST_LEAF_MINIMUM,
        max_features=config.DURATION_FOREST_FEATURE_SHARE,
        random_state=config.RANDOM_SEED,
        n_jobs=-1,
    )
    model = build_model_pipeline(
        estimator,
        config.DURATION_NUMERIC_FEATURES,
        config.DURATION_CATEGORICAL_FEATURES,
    )
    model.fit(train_features, train_target.astype(float))
    scores = evaluate_regressor(
        model, train_features, train_target, held_out_features, held_out_target
    )
    return model, scores
