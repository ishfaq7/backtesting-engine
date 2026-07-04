from btengine.integrations.ai_model import AIModelProvider


class ConformingModel:
    def predict(self, features):
        return {"score": sum(features.values())}


class NonConformingModel:
    def not_predict(self) -> None:
        pass


def test_conforming_class_satisfies_the_protocol() -> None:
    assert isinstance(ConformingModel(), AIModelProvider)


def test_nonconforming_class_does_not_satisfy_the_protocol() -> None:
    assert not isinstance(NonConformingModel(), AIModelProvider)


def test_conforming_instance_behaves_as_expected() -> None:
    model: AIModelProvider = ConformingModel()
    assert model.predict({"a": 1.0, "b": 2.0}) == {"score": 3.0}
