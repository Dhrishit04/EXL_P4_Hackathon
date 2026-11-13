from modelproof import tracking


def test_r_coefficient_names_become_valid_mlflow_keys():
    assert tracking._safe_key("coef.(Intercept)") == "coef.Intercept"
    assert tracking._safe_key("coef.woe_util") == "coef.woe_util"
