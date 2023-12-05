# Parameter meaning in parfile
* DILATEFREQ: whether or not to apply SS time dilation to RFs
* NE_SW:  Default value for electron density (cm-3) at 1AU due to solar wind
* TIMEEPH:
* T2CMETHOD: how to transform from terrestrial to celestial coords (e.g. FB90 or IAU2000B)
* TRES: rms post
* DM_SERIES (TAYLOR/POLY) (see: https://bitbucket.org/psrsoft/tempo2/issues/27/tempo2-dm-polynomial-is-not-a-taylor) Difference is division of coefficient by k! (order)



INPUT: list of parfiles/timfiles/timing packages (so for each par/tim file combination, we also know whether to use it as a tempopulsar or pintpulsar)

- Read in the parfiles using the PINT parfile parser (to check the basics)
- If all timescales are identical (either TDB or ECB), leave it. If mixed, convert the TCB ones to TDB using the PINT/Tempo2 tool.
  * If all same 'package' and all same 'UNITS', do nothing
  * Otherwise, convert all to TDB
- Check all binary models
  * If there are 'T2' models, figure out what the underlying model is:
    If there are EPS1/EPS2/H3 then it's ELL1H
    If there are EPS1/EPS2 then it's ELL1
    If there is H3, then DDH
    If there is SHAPMAX, then it's DDS
    If there is a KOM/KIN, then it's DDK
      NOTE: In Tempo2, it would then also need: SINI KIN
    If there is only PB/PBDOT/A1/A1DOT/OM/OMDOT/GAMMA/ECC/EDOT, then it's BT
    Otherwise it's DD
- If mixed PINT/Tempo2 pulsars, use a PINT pulsar Binary/Astrometry/Spin (BAS) parameters. Otherwise pick a random pulsar BAS parameters, including the PEPOCH/POSEPOCH parameters, and replace those in the other parfiles. Output the new parfiles as temporary files. The above procedure is deterministic, so we do not have to save the new parfiles (but we can, as an option)
- Remove all DMX lines, and make sure to add DM1 and DM2 if they aren't available yet. If DM1/DM2 is present somewhere, copy it over
- Make sure that the EPHEM version is set equal to the parfile where we copied the BAS parameters from
- Set PLANET_SHAPIRO equal (all 'Y') in all parfiles
- Load the pulsars separately as a new Enterprise 'metapulsar' object, and merge the BAS parameters in the design matrix.
- Use Enterprise as usual.