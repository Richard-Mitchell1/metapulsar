from pint.models import get_model_and_toas, get_model
from pint.models import model_builder as modbuild
from pint.residuals import Residuals
from pint.toa import get_TOAs
import pint.logging
import astropy.units as u

import glob, sys, os
import shutil
import numpy as np
import scipy.linalg as sl
import copy
from itertools import zip_longest

import xarray as xr
import arviz as az
import la_forge.core as co
import la_forge.diagnostics as dg


import metapulsar as mp
from h5pulsar import FilePulsar

import enterprise
import ephem
from enterprise.pulsar import Pulsar

import enterprise.signals.parameter as parameter
from enterprise.signals import utils
from enterprise.signals import signal_base
from enterprise.signals import selections
from enterprise.signals.selections import Selection
from enterprise.signals import white_signals
from enterprise.signals import gp_signals
from enterprise.signals import deterministic_signals

import enterprise_extensions.models as eem
import enterprise_extensions.blocks as eeb
import enterprise_extensions.sampler as ees
from PTMCMCSampler.PTMCMCSampler import PTSampler

import argparse



# Can select on multiple flags -- staggered (IPTA-like)
# "-group, None" (all for that flag)
# "-pta PPTA" (only that flag)
# "(group, f), None (all for group, if no group, all for f)"
def create_selection_stag(name, flagdict={}, lowfreq=None, highfreq=None):

    def get_flagvals(flags, flag, flagval):
        if flagval is not None:
            return [flagval]
        else:
            # Never use empty flag values
            return set(flags[flag]) - set([""])

    # Deprecated function
    #def combined_flag_mask(flags, flag, flagvals, msk_subset=None):
    #    msk = np.zeros_like(flags[flag], dtype=bool)
    #    msk_subset = msk if msk_subset is None else msk_subset

    #    for flagval in flagvals:
    #        msk_new = flags[flag]==flagval

    #        msk = np.logical_or(msk, np.logical_and(msk_subset, msk_new))

    #    return msk

    def get_flagit(flags, flag, flagval):
        """get_flagit(flags, ("group", "f"), None) -> {flagval_list: masks}"""
        try:
            if isinstance(flag, str):
                raise TypeError
            flagkeys = [f for f in flag]
        except TypeError:
            flagkeys = [flag]

        dummy_key = list(flags.keys())[0]
        msk_todo = np.ones_like(flags[dummy_key], dtype=bool)
        rd = {}

        for flagkey in flagkeys:
            try:
                flagvals = get_flagvals(flags, flagkey, flagval)
                for fv in flagvals:
                    #print(f"HERE: {flagkey} - {fv}")
                    #msk_comb = combined_flag_mask(flags, flagkey, flagvals, msk_todo)
                    msk_flag = (flags[flagkey] == fv)

                    #if np.any(np.logical_and(msk_todo, msk_comb)):
                    if np.any(np.logical_and(msk_todo, msk_flag)):
                        # Yep, add this flag-key
                        #print("Yup, adding")
                        #rd.update({fv: msk_comb})
                        rd.update({fv: msk_flag})

                        #msk_todo = np.logical_and(msk_todo, np.logical_not(msk_comb))
                        msk_todo = np.logical_and(msk_todo, np.logical_not(msk_flag))
                    else:
                        # Nothing to add
                        pass

            except KeyError:
                pass

        return rd

    def selection_func(flags, freqs):
        if lowfreq is not None and highfreq is not None:
            freq_mask = np.logical_and(freqs >= float(lowfreq), freqs <= float(highfreq))
            suffix = f"_B_{lowfreq}_{highfreq}"
        else:
            freq_mask = np.ones_like(freqs, dtype=bool)
            suffix = ""

        sels = [get_flagit(flags, flag, flagval) for (flag, flagval) in flagdict.items()]
        #print(flagdict)

        if len(sels) > 0:
            #print(sels)
            return {name+suffix+"_"+fv: msk for rd in sels for (fv, msk) in rd.items()}
        else:
            return {name + suffix: freq_mask}

    return selection_func


def build_ipta_model(psr, inc_ecorr=True):

    # EFAC and EQUAD by 'group'. If no 'group' exists, fallback to 'f'
    efeq_sel = selections.Selection(create_selection_stag("efacequad", {('group', 'f'): None}))

    # EFAC and EQUAD by 'B' (PPTA). If no 'group' exists, fallback to 'f' (NANOGrav)
    ecorr_sel = selections.Selection(create_selection_stag("ecorr", {('B', 'f'): None}))

    #band_sel = selections.Selection(create_selection_stag("ecorr", {'pta': "PPTA"}, 0, 960))
    no_sel = selections.Selection(selections.no_selection)

    # Multiple Ecorr doesn't work. Hack it in ourselves.
    ecorr = parameter.Uniform(-8.5, -5)
    efac = parameter.Uniform(0.01, 10.0)
    equad = parameter.Uniform(-8.5, -5)
    log10_A_dm = parameter.Uniform(-20, -11)
    gamma_dm = parameter.Uniform(0, 7)
    log10_A_rn = parameter.Uniform(-20, -11)
    gamma_rn = parameter.Uniform(0, 7)
    log10_A_rnf = parameter.Uniform(-20, -11)
    gamma_rnf = parameter.Uniform(0, 7)
    #log10_A_rnb = parameter.Uniform(-20, -11)
    #gamma_rnb = parameter.Uniform(0, 7)

    rn_pl = utils.powerlaw(log10_A=log10_A_rn, gamma=gamma_rn)
    rnf_pl = utils.powerlaw(log10_A=log10_A_rnf, gamma=gamma_rnf)
    #rnb_pl = utils.powerlaw(log10_A=log10_A_rnb, gamma=gamma_rnb)
    dm_pl = utils.powerlaw(log10_A=log10_A_dm, gamma=gamma_dm)
    dm_basis = utils.createfourierdesignmatrix_dm(nmodes=200)

    tm = gp_signals.MarginalizingTimingModel(use_svd=False)
    efeq = white_signals.MeasurementNoise(efac=efac, log10_t2equad=equad,
                                          selection=efeq_sel, name='white')
    ec = white_signals.EcorrKernelNoise(log10_ecorr=ecorr,
                                            selection=ecorr_sel,
                                            name='ecorr')

    dm = gp_signals.BasisGP(dm_pl, dm_basis, name='dm_gp', coefficients=False, selection=no_sel)

    rn = gp_signals.FourierBasisGP(rn_pl, components=11,
                                         coefficients=False,
                                         combine=True,selection=no_sel,
                                         name='red_noise')

    rnf = gp_signals.FourierBasisGP(rnf_pl, components=150,
                                         coefficients=False,
                                         combine=True,selection=no_sel,
                                         name='red_noise_flat')

    #rnb = gp_signals.FourierBasisGP(rnb_pl, components=100,
    #                                coefficients=False,
    #                                combine=True,selection=band_sel,
    #                                name='red_noise_band')

    model = tm + efeq + dm + rn + rnf


    if inc_ecorr:
        model += ec

    return signal_base.PTA([model(psr)])


def main():

    # Initialize parser
    parser = argparse.ArgumentParser(description="Process Job ID")

    # Adding argument
    parser.add_argument('--procid', metavar='N', type=int, # nargs='+',
                        help='An integer representing the Job ID')

    parser.add_argument('--hdf5_dir', metavar='N', type=str,
                        help='Input directory for hdf5 files',
                        default='/data/hdf5-pulsars/ipta-dr3-light/')

    parser.add_argument('--output_dir', metavar='N', type=str,
                        help='Output directory for MCMC chains',
                        default='/data/chains/')

    # Parse arguments
    args = parser.parse_args()

    # Access the integer argument
    job_number = args.procid
    hdf5_dir = args.hdf5_dir
    output_dir = args.output_dir

    # The pulsars
    h5_filenames = glob.glob(os.path.join(hdf5_dir) + '*.h5')

    # The noise models
    # Only one model for now
    #npsrs = len(pulsars)
    #ncombinations = len(combinations)
    #i_psr = int(job_number / ncombinations)
    #i_combination = int(job_number % ncombinations)

    metapsr = FilePulsar(h5_filenames[job_number])
    chaindir = os.path.join(output_dir, metapsr.name)

    # Check for PTA modeling flags:
    have_ecorr = (np.sum(metapsr.flags['pta']=='PPTA') + np.sum(metapsr.flags['pta']=='NANOGrav'))>0

    pta = build_ipta_model(metapsr, have_ecorr)

    xs = {par.name: par.sample() for par in pta.params}

    # dimension of parameter space
    ndim = np.sum([np.size(x) for x in xs.values()])

    sampler = ees.setup_sampler(
        pta,
        outdir=chaindir,
        resume=False,
        empirical_distr=None,
        groups=None,            # Groups are set automagically
        human="rvh",
        save_ext_dists=False,
        loglkwargs={},
        logpkwargs={})

    with open(os.path.join(chaindir, 'pars.txt'), 'w') as fp:
        for parname in pta.param_names:
            fp.write(f"{parname}\n")

    # sampler for N steps
    N = 1000000
    x0 = np.hstack([p.sample() for p in pta.params])
    sampler.sample(x0, N, SCAMweight=30, AMweight=15, DEweight=50, )


if __name__=="__main__":
    main()
