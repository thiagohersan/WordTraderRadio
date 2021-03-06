# -*- coding: utf-8 -*-

import urllib2, urllib, os, sys, shutil, wave, math, subprocess
import midifile

# escape space on filenames being sent to shell commands
def escSpace(s):
    return s.replace(" ", "\ ")

class Song:
    def __init__(self, filename, justForTheLyrics=False):
        self.filename = filename
        self.songname = os.path.basename(filename).replace(".kar", "")
        self.MP3S_DIR = "./mp3s/"+self.songname+"/"
        self.WAVS_DIR = self.MP3S_DIR.replace("mp3","wav")
        self.lyrics = None
        self.tonedSyls = None
        self.tonedWords = None
        self.firstNoteTime = None
        self.midi=midifile.midifile()
        self.midi.load_file(filename)
        self.FNULL = open(os.devnull, 'w')

        # some initial clean up
        karsyl = list(self.midi.karsyl)
        kartimes = list(self.midi.kartimes)
        for (i,s) in enumerate(karsyl):
            s = s.replace('/', ' ')
            s = s.replace('\\', ' ')
            s = s.replace('_',' ')
            s = s.replace('\"', '')
            s = s.replace('\'', '')
            s = s.replace(',', '')
            s = s.replace('.', '')
            s = s.replace('!', '')
            s = s.replace('?', '')
            karsyl[i] = s

        # get syllables and times
        syls = [(s,t) for (s,t) in zip(karsyl, kartimes) if s!='']

        # this is a long string with the lyrics
        self.lyrics = ""
        for (s,t) in syls:
            self.lyrics += s
        self.lyrics = self.lyrics.strip()
        print self.lyrics.decode('iso-8859-1')

        if (justForTheLyrics):
            return

        # only return non-empty syllables
        syls = [(s.decode('iso-8859-1').lower().encode('iso-8859-1'),t) for (s,t) in syls if s!='' and s!=' ']

        noteTrack = None
        # figure out which track has notes for the lyrics
        minDiff = -1
        candidatesForRemoval = []
        toneTempoList = []
        toneMedian = -1
        toneMax = -1
        firstNoteTime = -1
        for n in range(self.midi.ntracks):
            thisTrack = [v for v in self.midi.notes if v[4]==n]
            if (len(thisTrack) > 0):
                candidatesForRemoval.append(n)

                # deal with percussion tracks with lots of "notes"
                if len(thisTrack) < 2*len(syls):
                    currentSum = 0
                    numberOfSums = len(syls)
                    currentToneList = []
                    currentToneMin = -1
                    currentToneMax = -1
                    thisTracksFirstNoteTime = thisTrack[0][5]

                    for (s,t) in syls:
                        minDistance = -1
                        minDistanceTone = -1
                        minDistanceTempo = -1
                        for (i,v) in enumerate(thisTrack):
                            if (minDistance == -1) or abs(t-v[5])<minDistance:
                                minDistance = abs(t-v[5])
                                minDistanceTone = v[0]
                                minDistanceTempo = 0

                                ii = i
                                while (minDistanceTempo == 0) and (ii+1<len(thisTrack)):
                                    minDistanceTempo = thisTrack[ii][5]-v[5]
                                    ii += 1
                                if (minDistanceTempo == 0):
                                    ii = max(1,i)
                                    minDistanceTempo = thisTrack[ii][5]-thisTrack[ii-1][5]

                        currentSum = currentSum + minDistance*minDistance
                        currentToneList.append((minDistanceTone,minDistanceTempo))
                        if (currentToneMin == -1) or (minDistanceTone < currentToneMin):
                            currentToneMin = minDistanceTone
                        if (currentToneMax == -1) or (minDistanceTone > currentToneMax):
                            currentToneMax = minDistanceTone

                    if(minDiff == -1) or (currentSum/numberOfSums < minDiff):
                        minDiff = currentSum/numberOfSums
                        noteTrack = n
                        toneTempoList = currentToneList
                        firstNoteTime = thisTracksFirstNoteTime
                        toneMedian = int(currentToneMin + (currentToneMax-currentToneMin)/2)
                        toneMax = currentToneMax
                        toneSum = sum([tone for (tone,tempo) in toneTempoList])
                        print "tone(max, med, avg): %s %s %s"%(currentToneMax,toneMedian,toneSum/len(toneTempoList))

        if len(toneTempoList) > len(syls):
            toneTempoList = toneTempoList[0:len(syls)]
        if len(toneTempoList) < len(syls):
            syls = syls[0:len(toneTempoList)]

        if len(toneTempoList) != len(syls):
            print "tone list length doesn't equal syllable list length"
            sys.exit(0)

        ## zip tone array into syls
        ##     this keeps track of tones relative to median
        self.tonedSyls = [(s.strip(),t,p-toneMedian,d) for ((s,t),(p,d)) in zip(syls, toneTempoList)]
        self.firstNoteTime = firstNoteTime

        ## write out wav from stripped midi
        if not os.path.exists(self.WAVS_DIR):
            os.makedirs(self.WAVS_DIR)

        tracks2remove = [t for t in candidatesForRemoval if t!=noteTrack and t!=self.midi.kartrack]
        outFileKar = self.filename.replace(".kar", "__.kar")
        self.midi.write_file(self.filename, outFileKar, tracks2remove, None, noteTrack)
        outFileWav = "%s/00.%s.wav" % (self.WAVS_DIR,self.songname)
        midiParams = "-A 100 %s -OwM -o %s"%(outFileKar, outFileWav)
        subprocess.call('timidity '+midiParams, shell=True, stdout=self.FNULL, stderr=subprocess.STDOUT)
        os.remove(outFileKar)

        if (toneMax > 70):
            pitchParam = 70-toneMax
            inFileWav = "%s/xx.%s.wav" % (self.WAVS_DIR,self.songname)
            subprocess.call('mv %s %s'%(outFileWav, inFileWav), shell='True', stdout=self.FNULL, stderr=subprocess.STDOUT)

            stParams = "%s %s -pitch=%s" % (inFileWav, outFileWav, pitchParam)
            subprocess.call('soundstretch '+stParams, shell='True', stdout=self.FNULL, stderr=subprocess.STDOUT)
            subprocess.call('rm %s'%(inFileWav), shell='True', stdout=self.FNULL, stderr=subprocess.STDOUT)

        ## fix case where syllable has multiple syllables
        ultimateSyls = []
        for (s,t,p,d) in self.tonedSyls:
            for w in s.split():
                ultimateSyls.append((w,t,p,d))

        # get tuple of (word, (trigger-times), (pitches), duration)
        words = []
        sylIndex = 0
        for w in self.lyrics.decode('iso-8859-1').lower().encode('iso-8859-1').split():
            (s,t,p,d) = ultimateSyls[sylIndex]
            fromSyls = s
            tt = [t]
            pp = [p]
            dd = d
            sylIndex += 1
            while (fromSyls != w):
                (s,t,p,d) = ultimateSyls[sylIndex]
                fromSyls += s
                tt.append(t)
                pp.append(p)
                dd += d
                sylIndex += 1
            words.append((w,tt, pp, dd))

        ## put words with same start time back together
        ultimateWords = []
        i = 0
        while (i < len(words)):
            currentWord = words[i]
            ii = i+1
            while (ii < len(words)) and (words[i][1][0] == words[ii][1][0]):
                currentWord = words[i] if(words[i][3] > words[ii][3]) else words[ii]
                ii += 1
            i = ii
            ultimateWords.append(currentWord)

        self.tonedWords = ultimateWords

    def prepWordVoice(self, mWordTrader=None):
        ## hash for downloading initial files
        ##     this maps to (filename, audio length in seconds)
        wordHash = {}
        for (w,t,p,d) in self.tonedWords:
            # swap words
            if mWordTrader is not None:
                w_ = w
                w = mWordTrader.trade(w,'iso-8859-1').encode('iso-8859-1')
                print "%s %s"%(w_.decode('iso-8859-1'),w.decode('iso-8859-1'))
            wordHash[w] = None

        url = 'http://translate.google.com/translate_tts?tl=pt&q='
        header = { 'User-Agent' : 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)' }

        filesToBeDeleted = []
        if not os.path.exists(self.MP3S_DIR):
            os.makedirs(self.MP3S_DIR)
        if not os.path.exists(self.WAVS_DIR):
            os.makedirs(self.WAVS_DIR)

        for w in wordHash:
            toPronounce = w
            if w == 'rua':
                toPronounce = 'ruua'
            mp3FilePath = self.MP3S_DIR+w.decode('iso-8859-1')+'.mp3'
            wavFilePath = mp3FilePath.replace('mp3','wav')
            if not os.path.isfile(mp3FilePath):
                response = urllib2.urlopen(urllib2.Request(url+urllib.quote(toPronounce), None, header))
                responseBytes = response.read()
                f = open(mp3FilePath, 'wb')
                f.write(responseBytes)
                f.close()
            ffParams = "-y -i %s -ar 44100 %s"%(escSpace(mp3FilePath), escSpace(wavFilePath))
            subprocess.call('ffmpeg '+ffParams, shell=True, stdout=self.FNULL, stderr=subprocess.STDOUT)
            wavWave = wave.open(wavFilePath)
            wavLength = wavWave.getnframes()/float(wavWave.getframerate())
            wavWave.close()
            wordHash[w] = (wavFilePath, wavLength)
            filesToBeDeleted.append(escSpace(wavFilePath))

        voiceData = []
        voiceWriter = None
        for (i, (w_,t,p,d)) in enumerate(self.tonedWords):
            w = mWordTrader.trade(w_,'iso-8859-1').encode('iso-8859-1') if mWordTrader is not None else w_
            currentLength = wordHash[w][1]

            targetLength = max(d, 1e-6)

            tempoParam = (currentLength-targetLength)/targetLength*100.0
            tempoParam = tempoParam/1.5 if(currentLength < targetLength) else tempoParam

            outputFile = "%s/%s.wav" % (self.WAVS_DIR,i)
            stParams = "%s %s -tempo=%s" % (escSpace(wordHash[w][0]), outputFile, tempoParam)
            subprocess.call('soundstretch '+stParams, shell='True', stdout=self.FNULL, stderr=subprocess.STDOUT)
            filesToBeDeleted.append(outputFile)

            voiceReader = wave.open(outputFile)
            framerate = voiceReader.getframerate()
            sampwidth = voiceReader.getsampwidth()
            voiceBytes = voiceReader.readframes(voiceReader.getnframes())
            voiceFloats = wave.struct.unpack("%dh"%(len(voiceBytes)/sampwidth), voiceBytes)

            if (voiceWriter is None):
                voiceFilename = "%s/%s.wav" % (self.WAVS_DIR,"00.vox")
                if mWordTrader is not None:
                    voiceFilename = voiceFilename.replace(".wav", ".%s.wav"%mWordTrader.name)
                voiceWriter = wave.open(voiceFilename, 'w')
                voiceWriter.setparams((voiceReader.getnchannels(), sampwidth, framerate, 8, 'NONE', 'NONE'))

            # pad space between words with 0s
            # deal with case of overshooting (due to words with same start time)
            numZeros = (int((t[0]-self.firstNoteTime)*framerate) - len(voiceData))
            if(numZeros < 0) and (abs(numZeros) < len(voiceData)):
                for j in range(numZeros,0):
                    voiceData[j] *= 0.5
                    if (j-numZeros < len(voiceFloats)):
                        voiceData[j] += voiceFloats[j-numZeros]*0.5
                voiceFloats = voiceFloats[-numZeros:]

            voiceData += [0] * numZeros
            voiceData += voiceFloats

            # close voice wav
            voiceReader.close()

        print "writing to disk"
        voiceWriter.writeframes(wave.struct.pack("%dh"%len(voiceData), *voiceData))
        voiceWriter.close()

        # remove all temp wav files
        [os.remove(f) for f in filesToBeDeleted]
