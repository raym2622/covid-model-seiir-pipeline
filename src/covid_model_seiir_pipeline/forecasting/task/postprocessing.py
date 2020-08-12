from argparse import ArgumentParser, Namespace
import functools
import logging
import multiprocessing
from pathlib import Path
import shlex
from typing import Optional, List

import numpy as np
import pandas as pd

from covid_model_seiir_pipeline import static_vars
from covid_model_seiir_pipeline.forecasting.specification import ForecastSpecification
from covid_model_seiir_pipeline.forecasting.data import ForecastDataInterface

log = logging.getLogger(__name__)


def run_seir_postprocessing(forecast_version: str) -> None:
    forecast_spec = ForecastSpecification.from_path(
        Path(forecast_version) / static_vars.FORECAST_SPECIFICATION_FILE
    )
    data_interface = ForecastDataInterface.from_specification(forecast_spec)

    for scenario in forecast_spec.scenarios:
        infections, deaths, r_effective = load_output_data(scenario, data_interface)


def load_output_data(scenario: str, data_interface: ForecastDataInterface):
    _runner = functools.partial(
        load_output_data_by_draw,
        scenario=scenario,
        data_interface=data_interface,
    )
    draws = range(data_interface.get_n_draws())
    with multiprocessing.Pool(30) as pool:
        outputs = list(pool.map(_runner, draws))
    deaths, infections, r_effective = zip(*outputs)

    with multiprocessing.Pool(3) as pool:
        deaths, infections, r_effective = pool.map(concat_measure, [deaths, infections, r_effective])

    return infections, deaths, r_effective


def concat_measure(measure_data: List[pd.Series]) -> pd.DataFrame:
    return pd.concat(measure_data, axis=1)


def load_output_data_by_draw(draw_id: int, scenario: str, data_interface: ForecastDataInterface):
    draw_df = data_interface.load_outputs(scenario, draw_id)
    draw_df = draw_df.set_index(['location_id', 'date']).sort_index()
    deaths = draw_df['deaths'].rename(f'draw_{draw_id}')
    infections = draw_df['infections'].rename(f'draw_{draw_id}')
    r_effective = draw_df['r_effective'].rename(f'draw_{draw_id}')
    return deaths, infections, r_effective


def parse_arguments(argstr: Optional[str] = None) -> Namespace:
    """
    Gets arguments from the command line or a command line string.
    """
    log.info("parsing arguments")
    parser = ArgumentParser()
    parser.add_argument("--forecast-version", type=str, required=True)

    if argstr is not None:
        arglist = shlex.split(argstr)
        args = parser.parse_args(arglist)
    else:
        args = parser.parse_args()

    return args


def main():
    args = parse_arguments()
    run_seir_postprocessing(forecast_version=args.forecast_version)



if __name__ == '__main__':
    main()
