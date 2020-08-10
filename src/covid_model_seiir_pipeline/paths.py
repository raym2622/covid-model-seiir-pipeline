import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, ClassVar, Dict, Union

from parse import parse

from covid_shared.shell_tools import mkdir
from loguru import logger

DRAW_FILE_TEMPLATE = 'draw_{draw_id}.csv'
LOCATION_FILE_TEMPLATE = 'location_{location_id}.csv'


@dataclass
class Paths:
    """Shared interface for concrete paths objects that represent
    local directory structures.

    """
    root_dir: Path
    read_only: bool = field(default=True)

    @property
    @abc.abstractmethod
    def directories(self) -> List[Path]:
        """Returns all top level sub-directories."""
        raise NotImplementedError

    def make_dirs(self):
        """Builds the local directory structure."""
        if self.read_only:
            raise RuntimeError(f"Tried to create directory structure when "
                               f"{self.__class__.__name__} was in read_only mode. "
                               f"Try instantiating with read_only=False.")

        logger.debug(f'Creating sub-directory structure for {self.__class__.__name__} '
                     f'in {self.root_dir}.')
        for directory in self.directories:
            mkdir(directory, parents=True, exists_ok=True)


@dataclass
class ScenarioPaths(Paths):
    """Local directory structure of a forecasting data root."""
    beta_scaling_file: ClassVar[str] = DRAW_FILE_TEMPLATE
    component_file: ClassVar[str] = DRAW_FILE_TEMPLATE
    outputs_file: ClassVar[str] = DRAW_FILE_TEMPLATE

    @property
    def beta_scaling(self) -> Path:
        """Scaling factors used to align past and forecast betas."""
        return self.root_dir / 'beta_scaling'

    def get_beta_scaling_path(self, draw_id: int) -> Path:
        """Retrieves a location specific path to beta scaling parameters"""
        return self.beta_scaling / self.beta_scaling_file.format(draw_id=draw_id)

    @property
    def components(self) -> Path:
        """Folders by location with SEIIR components."""
        return self.root_dir / 'component_draws'

    def get_components_path(self, draw_id: int) -> Path:
        """Get SEIIR components for a particular location and draw."""
        return self.components / self.component_file.format(draw_id=draw_id)

    @property
    def outputs(self) -> Path:
        """Cases, deaths, and effective R."""
        return self.root_dir / 'outputs'

    def get_outputs_path(self, draw_id: int) -> Path:
        """Single draw of forecast outputs."""
        return self.outputs / self.outputs_file.format(draw_id=draw_id)

    @property
    def directories(self) -> List[Path]:
        """Returns all top level sub-directories."""
        return [self.beta_scaling, self.components, self.outputs]


@dataclass
class ForecastPaths(Paths):
    scenarios: List[str] = field(default_factory=list)
    scenario_paths: Dict[str, ScenarioPaths] = field(init=False)

    def __post_init__(self):
        self.scenario_paths = {scenario: ScenarioPaths(self.root_dir / scenario, self.read_only)
                               for scenario in self.scenarios}

    @property
    def forecast_specification(self) -> Path:
        return self.root_dir / 'forecast_specification.yaml'

    def get_beta_scaling_path(self, draw_id: int, scenario: str) -> Path:
        return self.scenario_paths[scenario].get_beta_scaling_path(draw_id)

    def get_components_path(self, draw_id: int, scenario: str) -> Path:
        return self.scenario_paths[scenario].get_components_path(draw_id)

    def get_outputs_path(self, draw_id: int, scenario: str) -> Path:
        return self.scenario_paths[scenario].get_outputs_path(draw_id)

    def make_dirs(self):
        for scenario_paths in self.scenario_paths.values():
            scenario_paths.make_dirs()


@dataclass
class RegressionPaths(Paths):
    # class attributes are inferred using ClassVar. See pep 557 (Class Variables)
    beta_param_file: ClassVar[str] = DRAW_FILE_TEMPLATE
    date_file: ClassVar[str] = DRAW_FILE_TEMPLATE
    coefficient_file: ClassVar[str] = DRAW_FILE_TEMPLATE
    beta_regression_file: ClassVar[str] = DRAW_FILE_TEMPLATE
    data_file: ClassVar[str] = DRAW_FILE_TEMPLATE

    @property
    def location_metadata(self) -> Path:
        return self.root_dir / 'locations.yaml'

    @property
    def regression_specification(self):
        return self.root_dir / 'regression_specification.yaml'

    @property
    def parameters_dir(self) -> Path:
        return self.root_dir / 'parameters'

    def get_beta_param_file(self, draw_id: int) -> Path:
        return self.parameters_dir / self.beta_param_file.format(draw_id=draw_id)

    @property
    def date_dir(self) -> Path:
        return self.root_dir / 'dates'

    def get_date_file(self, draw_id: int) -> Path:
        return self.date_dir / self.date_file.format(draw_id=draw_id)

    @property
    def beta_regression_dir(self) -> Path:
        return self.root_dir / 'beta'

    def get_beta_regression_file(self, draw_id: int) -> Path:
        return self.beta_regression_dir / self.beta_regression_file.format(draw_id=draw_id)

    @property
    def coefficient_dir(self) -> Path:
        return self.root_dir / 'coefficients'

    def get_coefficient_file(self, draw_id: int) -> Path:
        return self.coefficient_dir / self.coefficient_file.format(draw_id=draw_id)

    @property
    def data_dir(self) -> Path:
        return self.root_dir / 'data'

    def get_data_file(self, draw_id: int) -> Path:
        return self.data_dir / self.data_file.format(draw_id=draw_id)

    @property
    def directories(self) -> List[Path]:
        """Returns all top level sub-directories."""
        return [self.parameters_dir, self.date_dir,
                self.beta_regression_dir, self.coefficient_dir,
                self.data_dir]


@dataclass
class InfectionPaths(Paths):
    # class attributes are inferred using ClassVar. See pep 557 (Class Variables)
    infection_file: ClassVar[str] = 'draw{draw_id:04}_prepped_deaths_and_cases_all_age.csv'

    def __post_init__(self):
        if not self.read_only:
            raise RuntimeError('Infection outputs should always be read only.')

    @property
    def directories(self) -> List[Path]:
        return []

    def get_location_dir(self, location_id: int):
        matches = [m for m in self.root_dir.glob(f"*_{location_id}")]
        num_matches = len(matches)
        if num_matches > 1:
            raise RuntimeError("There is more than one location-specific folder for "
                               f"{location_id}.")
        elif num_matches == 0:
            raise FileNotFoundError("There is not a location-specific folder for "
                                    f"{location_id}.")
        else:
            folder = matches[0]
        return self.root_dir / folder

    def get_modelled_locations(self) -> List[int]:
        """Retrieve all of the location specific infection directories."""
        return [int(p.name.split('_')[-1]) for p in self.root_dir.iterdir() if p.is_dir()]

    def get_infection_file(self, location_id: int, draw_id: int) -> Path:
        # folder = _get_infection_folder_from_location_id(location_id, self.infection_dir)
        f = (self.get_location_dir(location_id) / self.infection_file.format(draw_id=draw_id))
        return f


@dataclass
class CovariatePaths(Paths):
    # class attributes are inferred using ClassVar. See pep 557 (Class Variables)

    scenario_file: ClassVar[str] = "{scenario}_scenario.csv"

    def __post_init__(self):
        if not self.read_only:
            raise RuntimeError('Covariate outputs should always be read only.')

    @property
    def directories(self) -> List[Path]:
        return []

    def get_covariate_dir(self, covariate: str) -> Path:
        return self.root_dir / covariate

    def get_covariate_scenario_file(self, covariate: str, scenario: str):
        return self.root_dir / covariate / self.scenario_file.format(scenario=scenario)

    def get_covariate_scenario_to_file_mapping(self, covariate: str) -> Dict[str, Path]:
        covariate_dir = self.get_covariate_dir(covariate)
        matches = [m for m in covariate_dir.glob(self.scenario_file.format(scenario="*"))]
        mapping = {}
        for file in matches:
            key = parse(self.scenario_file, str(file.name))["scenario"]
            file = covariate_dir / file
            mapping[key] = file
        return mapping

    def get_info_files(self, covariate: str) -> List[Path]:
        covariate_dir = self.get_covariate_dir(covariate)
        matches = [covariate_dir / m for m in covariate_dir.glob(f"*info.csv")]
        return matches