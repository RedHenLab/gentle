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
  resultJSON = json.loads(result.to_json(indent=2))
  transText = resultJSON['transcript']
  wordsLen = len(resultJSON['words'])

  lastStartOffset = 0
      
  prePunctuation = ""
  postPunctuation = ""

  for index, item in enumerate(resultJSON['words']):

    if (item['case'] == "success"):

      # Special case: first word is preceded by puncutation
      if ((index == 0) and (int(item['startOffset']) > 0)):
        prePunctuation = transText[0:int(item['startOffset'])].strip()

      # Final case: last word
      if (index == (wordsLen - 1)):
        postPunctuation = transText[int(item['endOffset']):len(transText)].strip()
        withPunctuation = prePunctuation + item['word'] + postPunctuation
      else: # (index <= (wordsLen - 1)):
        nextOffset = resultJSON['words'][index + 1]['startOffset']
        postPunctuation = transText[int(item['endOffset']):int(nextOffset)].strip()

        # Case in which there are multiple instances of punctuation separated
        # by spaces between this token and the next one. Attach the first
        # instance to this word, and the last to the next word.
        postPunctArray = postPunctuation.split(' ')
        if (len(postPunctArray) > 1):
          postPunctuation = punctArray[0].strip()
          withPunctuation = prePunctuation + item['word'] + postPunctutation
          prePunctuation = punctArray[-1].strip()
        else:
          prePunctuation = ""
          withPunctuation = item['word'] + postPunctuation

      line = {'word': item['word'], 'start': item['start'], 'end': item['end'], 'withPunctuation': withPunctuation}
          
    else:
      line = {'word': item['word'], 'start': 'NA', 'end': 'NA', 'withPunctuation': 'NA'}
    json.dump(line, fh)
    fh.write("\n")
else: # (args.format == 'json'):
  fh.write(result.to_json(indent=2))

if args.output:
    logging.info("output written to %s" % (args.output))
