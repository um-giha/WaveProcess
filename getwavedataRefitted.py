# -*- coding: utf-8 -*-
"""
GetWaveData is a function that uses Waveform and Data loader, along with a 
configuration file to return basic waveform information.
Created on Wed Dec  7 06:19:10 2016

@author: Marc
"""

import numpy as np
import sys
import platform
import time
import configparser


def GetWaveDataR(configFileName, directoryName, fileNum = 1, getZeroCrossingIntegral=True):
    startTime = time.time()
    print("Running GetWaveData!")
    print("Starting at " + time.strftime('%H:%M:%S'))
    config = configparser.ConfigParser()
    config.read(configFileName)
    
    # Setup data info
    # Directories
    
    data_directory = directoryName # New
    
    data_file_name = config['Directories']['data_file_name']
    #pywaves_directory = config['Directories']['pywaves_directory']
    
    # Digitizer
    dataFormatStr = config['Digitizer']['dataFormat']
    nSamples = int(config['Digitizer']['samples_per_waveform'])
    ns_per_sample = int(config['Digitizer']['ns_per_sample'])
    number_of_bits = int(config['Digitizer']['number_of_bits'])
    dynamic_range_volts = float(config['Digitizer']['dynamic_range_volts'])
    polarity0 = int(config['Digitizer']['polarity0']) # Polarity of first several channels
    p0ch = int(config['Digitizer']['p0ch']) # Number of channels to apply first polarity to
    polarity1 = int(config['Digitizer']['polarity1']) # Polarity of remaining channels
    baselineOffset = int(config['Digitizer']['baseline_offset'])
    nBaselineSamples = int(config['Digitizer']['baseline_samples'])
    nCh = int(config['Digitizer']['number_of_channels'])
    
    # nWavesPerLoad = int(config['Data Management']['waves_per_load'])
    nWavesPerLoad = 10000 # Chosen pretty arbitrarily
    # nWaves = int(config['Data Management']['waves_per_folder']) # per folder
    nWaves = 1000000 # Large number
    # Let's just do all of the folders!
    startFolder = int(config['Data Management']['start_folder'])
    nFolders = fileNum
    # nFolders = int(config['Data Management']['number_of_folders'])
    
    unevenFactor = int(config['Data Management']['uneven_factor'])
    cfdFraction = float(config['Pulse Processing']['cfd_fraction'])
    integralEnd = int(config['Pulse Processing']['integral_end'])
    totalIntegralStart = int(config['Pulse Processing']['total_integral_start'])
    tailIntegralStart = int(config['Pulse Processing']['tail_integral_start'])
    applyCRRC4 = bool(int(config['Pulse Processing']['apply_crrc4']))
    CRRC4Tau = float(config['Pulse Processing']['crrc4_shaping_time'])
    
    # Load pywaves
   # sys.path.extend([pywaves_directory])
    from dataloader import DataLoader
    from waveform import Waveform
    
    # Pre-calc
    if dataFormatStr == 'DPP_MIXED':
        dataFormat = DataLoader.DAFCA_DPP_MIXED
    elif dataFormatStr == 'STANDARD':
        dataFormat = DataLoader.DAFCA_STD
    if platform.system() is 'Windows':
        directory_separator  = '\\'
    else:
        directory_separator  = '/'
        
    # Initialize data arrays
    dataFile1 = data_directory + directory_separator + str(1) + directory_separator + data_file_name
    datloader1 = DataLoader(dataFile1,dataFormat,nSamples)
    nWavesIn1 = datloader1.GetNumberOfWavesInFile()
    # print(str(nWavesIn1))
    
    nLoads = int(nWavesIn1/nWavesPerLoad)
    if nLoads < 1:
        nLoads = 1
    chBufferSize = int(nFolders*nWavesIn1*unevenFactor/nCh)
    VperLSB = dynamic_range_volts/(2**number_of_bits)
    fileTimeGap = 2**43 # Note: no more than 3 hours per measurement!
    
    # Setup channel queues
    ph = np.zeros((nCh,chBufferSize))
    amp = np.zeros((nCh,chBufferSize))
    tailInt = np.zeros((nCh,chBufferSize))
    totalInt = np.zeros((nCh,chBufferSize))
    rms = np.zeros((nCh,chBufferSize))
    ttt = np.zeros((nCh,chBufferSize), dtype=np.uint32)
    extras = np.zeros((nCh,chBufferSize), dtype=np.uint32)
    fullTime = np.zeros((nCh,chBufferSize), dtype=np.uint64)
    cfd = np.zeros((nCh,chBufferSize))
    chCount = np.zeros(nCh, dtype=np.uint32)
    flags = np.zeros((nCh,chBufferSize), dtype=np.uint32)
    
    # Setup data loader
    waveform = Waveform(np.zeros(nSamples), polarity0, baselineOffset, nBaselineSamples)
    print( 'polarity0 =' + str( polarity0 ) )
    print( 'p0ch = ' + str( p0ch) )
    print( 'polarity1 =' + str( polarity1 ) )
    
    # Queue up waves
    for f in range(startFolder, startFolder+nFolders):
        print('Folder {}:'.format(f))    
        fullDFileName = data_directory + directory_separator + str(f) + directory_separator + data_file_name
        datloader = DataLoader(fullDFileName,dataFormat,nSamples)
        nWavesInFile = datloader.GetNumberOfWavesInFile()
        nWaves = nWavesInFile + 1
        if (nWavesInFile < nWaves):
            print('Warning: requested more waves than exists in file!')
            loadsInFile = int(np.ceil(nWavesInFile/nWavesPerLoad))
            print('Loading all {} waves instead...'.format(nWavesInFile))
            lastLoad = nWavesInFile - (loadsInFile-1)*nWavesPerLoad
        else:
            loadsInFile = nLoads
            lastLoad = nWavesPerLoad
        if nWavesInFile % 2 == 0 or nWavesInFile % 2 == 1 or int(nCh) == 2:
            for load in range(loadsInFile):
                if(load == loadsInFile-1):
                    wavesThisLoad = lastLoad
                else:
                    wavesThisLoad = nWavesPerLoad
                waves = datloader.LoadWaves(wavesThisLoad)
                for w in range(wavesThisLoad):
                    ch = waves[w]['Channel']
                    waveform.SetSamples(waves[w]['Samples'])
                    if (ch >= p0ch):
                        waveform.Polarize(polarity1)
                    else:
                        waveform.Polarize(polarity0)
                    #print(str( waveform.polarity))
                    if applyCRRC4:
                        waveform.ApplyCRRC4(ns_per_sample, CRRC4Tau)
                    if getZeroCrossingIntegral:
                        ph[ch][chCount[ch]] = waveform.GetIntegralToZeroCrossing()*VperLSB*ns_per_sample
                    amp[ch][chCount[ch]] = waveform.GetMax()
                    tailInt[ch][chCount[ch]] = waveform.GetIntegralFromPeak(tailIntegralStart,integralEnd)*VperLSB*ns_per_sample
                    totalInt[ch][chCount[ch]] = waveform.GetIntegralFromPeak(totalIntegralStart,integralEnd)*VperLSB*ns_per_sample
                    cfd[ch][chCount[ch]] = waveform.GetCFDTime(cfdFraction)*ns_per_sample
                    ttt[ch][chCount[ch]] = waves[w]['TimeTag']
                    rms[ch][chCount[ch]] = waveform.GetRMSbls(nBaselineSamples)
                    if dataFormatStr == 'DPP_MIXED':                
                        extras[ch][chCount[ch]] = waves[w]['Extras']
#                    fullTime[ch][chCount[ch]] = ((waves[w]['TimeTag'] + 
#                                                ((waves[w]['Extras'] & 0xFFFF0000)
#                                                << 15)))*ns_per_sample
                        fullTime[ch][chCount[ch]] = ((waves[w]['TimeTag'] + 
                                                ((waves[w]['Extras'] & 0xFFFF0000)
                                                << 15)) + fileTimeGap*f)*ns_per_sample
                    chCount[ch] += 1
    endTime = time.time()
    runTime = endTime - startTime
    print("GetWaveDataR took {} s".format(runTime))
    return chCount, ph, amp, tailInt, totalInt, cfd, ttt, extras, fullTime, flags, rms