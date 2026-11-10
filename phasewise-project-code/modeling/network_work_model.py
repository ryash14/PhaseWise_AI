"""The network work model: how likely an application is to need work on the network."""

from sklearn.linear_model import LogisticRegression

from config import config
from data_pipeline.feature_builder import build_model_pipeline
from modeling.model_evaluation import evaluate_classifier


def train_network_work_model(train_features, train_target, held_out_features,
                             held_out_target):
    """Fit a calibrated logistic regression on the training applications only."""
    estimator = LogisticRegression(
        max_iter=config.NETWORK_WORK_MODEL_MAXIMUM_ITERATIONS,
        random_state=config.RANDOM_SEED,
    )
    model = build_model_pipeline(
        estimator,
        config.NETWORK_WORK_NUMERIC_FEATURES,
        config.NETWORK_WORK_CATEGORICAL_FEATURES,
    )
    model.fit(train_features, train_target.astype(int))
    scores = evaluate_classifier(
        model, train_features, train_target, held_out_features, held_out_target
    )
    return model, scores
