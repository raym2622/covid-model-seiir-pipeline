from covid_shared import cli_tools
from loguru import logger

from covid_model_seiir_pipeline.forecasting.specification import ForecastSpecification
from covid_model_seiir_pipeline.forecasting.data import ForecastDataInterface
from covid_model_seiir_pipeline.forecasting.workflow import ForecastWorkflow


def do_beta_forecast(app_metadata: cli_tools.Metadata,
                     forecast_specification: ForecastSpecification):
    logger.debug('Starting beta forecast.')

    data_interface = ForecastDataInterface.from_specification(forecast_specification)

    # Check scenario covariates the same as regression covariates and that
    # covariate data versions match.
    data_interface.check_covariates(forecast_specification.scenarios)

    data_interface.make_dirs()
    # Fixme: Inconsistent data writing interfaces
    forecast_specification.dump(data_interface.forecast_paths.forecast_specification)

    forecast_wf = ForecastWorkflow(forecast_specification.data.output_root)
    n_draws = data_interface.get_n_draws()
    forecast_wf.attach_scenario_tasks(n_draws=n_draws,
                                      scenarios=list(forecast_specification.scenarios))
    forecast_wf.run()