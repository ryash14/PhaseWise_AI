"""The sentence model: names the type of each sentence of an installer's statement."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from config import config
from modeling.model_evaluation import evaluate_text_classifier


def train_sentence_model(train_text, train_target, held_out_text, held_out_target):
    """Fit TF-IDF word and word-pair features with a balanced logistic regression."""
    model = Pipeline(
        [
            (
                config.PREPROCESSING_STEP_NAME,
                TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, lowercase=True),
            ),
            (
                config.MODEL_STEP_NAME,
                LogisticRegression(
                    C=10.0,
                    class_weight="balanced",
                    max_iter=config.SENTENCE_MODEL_MAXIMUM_ITERATIONS,
                    random_state=config.RANDOM_SEED,
                ),
            ),
        ]
    )
    model.fit(list(train_text), list(train_target))
    scores = evaluate_text_classifier(
        model, train_text, train_target, held_out_text, held_out_target
    )
    return model, scores
