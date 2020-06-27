from pathlib import Path
from typing import List, Dict, Tuple

import pandas as pd
import yaml

from covid_model_seiir_pipeline import paths
from covid_model_seiir_pipeline.regression.specification import RegressionSpecification
from covid_model_seiir_pipeline.static_vars import COVARIATE_COL_DICT


class RegressionDataInterface:

    covariate_scenario_val = "{covariate}_{scenario}"

    def __init__(self,
                 regression_paths: paths.RegressionPaths,
                 ode_paths: paths.ODEPaths,
                 covariate_paths: paths.CovariatePaths):
        self.regression_paths = regression_paths
        self.ode_paths = ode_paths
        self.covariate_paths = covariate_paths

    @classmethod
    def from_specification(cls, specification: RegressionSpecification) -> 'RegressionDataInterface':
        regression_paths = paths.RegressionPaths(Path(specification.data.output_root), read_only=False)
        ode_paths = paths.ODEPaths(Path(specification.data.ode_fit_version))
        covariate_paths = paths.CovariatePaths(Path(specification.data.covariate_version))
        return cls(
            regression_paths=regression_paths,
            ode_paths=ode_paths,
            covariate_paths=covariate_paths
        )

    #####################
    # ODE paths loaders #
    #####################

    def load_location_ids(self) -> List[int]:
        with self.ode_paths.location_metadata.open() as location_file:
            location_ids = yaml.full_load(location_file)
        return location_ids

    def load_ode_fits(self, location_ids: List[int], draw_id: int) -> pd.DataFrame:
        df_beta = []
        for l_id in location_ids:
            df_beta.append(pd.read_csv(self.ode_paths.get_draw_beta_fit_file(l_id, draw_id)))
        df_beta = pd.concat(df_beta).reset_index(drop=True)
        return df_beta

    def get_draw_count(self) -> int:
        with self.ode_paths.fit_specification.open() as fit_spec_file:
            fit_spec = yaml.full_load(fit_spec_file)
        return fit_spec['parameters']['n_draws']

    ###########################
    # Covariate paths loaders #
    ###########################

    def load_covariate(self,
                       covariate: str,
                       location_ids: List[int],
                       draw_id: int,
                       use_draws: bool) -> Dict[str, pd.DataFrame]:
        covariate_set: Dict[str, pd.DataFrame] = {}
        scenario_map = self.covariate_paths.get_covariate_scenario_to_file_mapping(covariate)

        for scenario, input_file in scenario_map.items():
            # name of scenario value column
            if use_draws:
                val_name = f"draw_{draw_id}"
            else:
                val_name = self.covariate_scenario_val.format(covariate=covariate,
                                                              scenario=scenario)

            regress_df, scenario_df = self._load_scenario_file(val_name, input_file,
                                                               location_ids, draw_id)
            # change name of scenario data
            scenario_val_name = self.covariate_scenario_val.format(covariate=covariate,
                                                                   scenario=scenario)
            scenario_df = scenario_df.rename(columns={val_name: scenario_val_name})
            # change name of regression data to be covariate name
            regress_df = regress_df.rename(columns={val_name: covariate})

            # store regress data only once
            cached_df = covariate_set.get(covariate)
            if cached_df is None:
                covariate_set[covariate] = regress_df.reset_index(drop=True)
            else:
                if not cached_df.equals(regress_df.reset_index(drop=True)):
                    raise RuntimeError(
                        "Regression data is not exactly equal between covariates in covariate "
                        f"pool. Input files are {scenario_map.values()}.")

            covariate_set[scenario_val_name] = scenario_df

        return covariate_set

    def _load_scenario_file(self, val_name: str, input_file: Path, location_ids: List[int],
                            draw_id: int
                            ) -> Tuple[pd.DataFrame, pd.DataFrame]:

        # read in covariate
        df = pd.read_csv(str(input_file))
        columns = [COVARIATE_COL_DICT['COL_LOC_ID'], val_name]

        # drop nulls
        df = df.loc[~df[val_name].isnull()]

        # subset locations
        df = df.loc[df[COVARIATE_COL_DICT['COL_LOC_ID']].isin(location_ids)]

        # is time dependent cov? filter by time series
        if COVARIATE_COL_DICT['COL_DATE'] in df.columns:
            columns.append(COVARIATE_COL_DICT['COL_DATE'])

            # read in cutoffs
            # TODO: not optimized because we read in multiple covariates, but data is small
            cutoffs = pd.read_csv(self.ode_paths.get_draw_date_file(draw_id))
            cutoffs = cutoffs.rename(columns={"loc_id": COVARIATE_COL_DICT['COL_LOC_ID']})
            cutoffs = cutoffs.loc[cutoffs[COVARIATE_COL_DICT['COL_LOC_ID']].isin(location_ids)]
            df = df.merge(cutoffs, how="left")

            # get what was used for ode_fit
            # TODO: should we inclusive inequality sign?
            regress_df = df[df.date <= df.end_date].copy()
            regress_df = regress_df[columns]

            # get what we will use in scenarios
            # TODO: should we inclusive inequality sign?
            scenario_df = df[df.date >= df.end_date].copy()
            scenario_df = scenario_df[columns]

        # otherwise just make 2 copies
        else:
            regress_df = df.copy()
            scenario_df = df

            # subset columns
            regress_df = regress_df[columns]
            scenario_df = scenario_df[columns]

        return regress_df, scenario_df

    def save_covariates(self, df: pd.DataFrame, draw_id: int) -> None:
        path = self.regression_paths.get_covariates_file(draw_id)
        df.to_csv(path, index=False)

    def save_scenarios(self, df: pd.DataFrame, draw_id: int) -> None:
        location_ids = df[COVARIATE_COL_DICT['COL_LOC_ID']].tolist()
        for l_id in location_ids:
            loc_scenario_df = df.loc[df[COVARIATE_COL_DICT['COL_LOC_ID']] == l_id]
            scenario_file = self.regression_paths.get_scenarios_file(l_id, draw_id)
            loc_scenario_df.to_csv(scenario_file, index=False)

    def load_mr_coefficients(self, draw_id: int) -> pd.DataFrame:
        return pd.read_csv(self.regression_paths.get_draw_coefficient_file(draw_id))

    def save_regression_betas(self, df: pd.DataFrame, draw_id: int, location_ids: List[int]
                              ) -> None:
        for l_id in location_ids:
            loc_beta_fits = df.loc[df[COVARIATE_COL_DICT['COL_LOC_ID']] == l_id]
            beta_file = self.regression_paths.get_draw_beta_regression_file(l_id, draw_id)
            loc_beta_fits.to_csv(beta_file, index=False)

    def load_regression_betas(self, location_id: int, draw_id: int):
        beta_file = self.regression_paths.get_draw_beta_regression_file(location_id, draw_id)
        return pd.read_csv(beta_file)
