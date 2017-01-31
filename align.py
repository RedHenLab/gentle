import argparse
import logging
import multiprocessing
import os
import sys
import json

import gentle

parser = argparse.ArgumentParser(
        description='Align a transcript to audio by generating a new language model.  Outputs JSON')
parser.add_argument(
        '--nthreads', default=multiprocessing.cpu_count(), type=int,
        help='number of alignment threads')
parser.add_argument(
        '-o', '--output', metavar='output', type=str, 
        help='output filename')
parser.add_argument(
        '-f', '--format', default='json', metavar='format', type=str, 
        help='output format')
parser.add_argument(
        '--conservative', dest='conservative', action='store_true',
        help='conservative alignment')
parser.set_defaults(conservative=False)
parser.add_argument(
        '--disfluency', dest='disfluency', action='store_true',
        help='include disfluencies (uh, um) in alignment')
parser.set_defaults(disfluency=False)
parser.add_argument(
        '--log', default="INFO",
        help='the log level (DEBUG, INFO, WARNING, ERROR, or CRITICAL)')
parser.add_argument(
        'audiofile', type=str,
        help='audio file')
parser.add_argument(
        'txtfile', type=str,
        help='transcript text file')
args = parser.parse_args()

log_level = args.log.upper()
logging.getLogger().setLevel(log_level)

disfluencies = set(['uh', 'um'])

def on_progress(p):
    for k,v in p.items():
        logging.debug("%s: %s" % (k, v))


with open(args.txtfile) as fh:
    transcript = fh.read()

resources = gentle.Resources()
logging.info("converting audio to 8K sampled wav")

with gentle.resampled(args.audiofile) as wavfile:
    logging.info("starting alignment")
    aligner = gentle.ForcedAligner(resources, transcript, nthreads=args.nthreads, disfluency=args.disfluency, conservative=args.conservative, disfluencies=disfluencies)
    result = aligner.transcribe(wavfile, progress_cb=on_progress, logging=logging)

fh = open(args.output, 'w') if args.output else sys.stdout

if (args.format == 'jsonl'):
  #rawJSON = json.loads(result.to_json(indent=2))
  #resultJSON = {'transcript': rawJSON['transcript'], 'words': []}
  #for item in rawJSON['words']:
  #  if (item['case'] == "success"):
  #    resultJSON['words'].append(item) 

  resultJSON = json.loads(result.to_json(indent=2))
  transText = resultJSON['transcript']
  wordsLen = len(resultJSON['words'])

  lastStartOffset = 0
      
  prePunctuation = ""
  postPunctuation = ""

  for index, item in enumerate(resultJSON['words']):

    # If "include disfluencies" is enabled, gentle will insert detected "ums"
    # and "ahs", etc. with valid time codes but no offsets in the transcript
    # (because they aren't transcribed).
    if ((item['case'] == "success") or (item['case'] == 'not-found-in-transcript')):

      prePunctuation = ""
      postPunctuation = ""
      prePunctLine = None
      postPunctLine = None

      # Special case: first word is preceded by puncutation
      if ((index == 0) and (item['case'] == "success") and (int(item['startOffset']) > 0)):
        prePunctuation = transText[0:int(item['startOffset'])].strip()
        if (prePunctuation != ""):
          prePunctLine = {'punctuation': prePunctuation}

      # Final case: last word
      if ((index == (wordsLen - 1)) and (item['case'] == "success")):
        postPunctuation = transText[int(item['endOffset']):len(transText)].strip()
        if (postPunctuation != ""):
          postPunctLine = {'punctuation': postPunctuation}

      else: # (index <= (wordsLen - 1)):

        if ((item['case'] == "success") and (resultJSON['words'][index + 1]['case'] == "success")):
          nextOffset = resultJSON['words'][index + 1]['startOffset']
          postPunctuation = transText[int(item['endOffset']):int(nextOffset)].strip()
        if (postPunctuation != ""):
          postPunctLine = {'punctuation': postPunctuation}

      if (prePunctLine is not None):
        json.dump(prePunctLine, fh)
        fh.write("\n")

      line = {'word': item['word'], 'start': "{0:.2f}".format(item['start']), 'end': "{0:.2f}".format(item['end'])}
      json.dump(line, fh)
      fh.write("\n")

      if (postPunctLine is not None):
        json.dump(postPunctLine, fh)
        fh.write("\n")

    else:
      line = {'word': item['word'], 'start': 'NA', 'end': 'NA'}
      json.dump(line, fh)
      fh.write("\n")
else: # (args.format == 'json'):
  fh.write(result.to_json(indent=2))

if args.output:
    logging.info("output written to %s" % (args.output))
