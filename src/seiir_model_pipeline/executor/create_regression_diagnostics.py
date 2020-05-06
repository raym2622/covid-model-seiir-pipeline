from argparse import ArgumentParser
import logging

from seiir_model.visualizer.visualizer import PlotBetaCoef, PlotBetaResidual

from seiir_model_pipeline.core.versioner import args_to_directories

log = logging.getLogger(__name__)


def get_args():
    """
    Gets arguments from the command line.
    """
    parser = ArgumentParser()
    parser.add_argument("--regression-version", type=str, required=True)

    return parser.parse_args()


def main():
    args = get_args()
    log.info("Initiating SEIIR diagnostics.")

    # Load metadata
    directories = args_to_directories(args)

    handle = PlotBetaCoef(directories)
    handle.plot_coef()

    handle = PlotBetaResidual(directories)
    handle.plot_residual()