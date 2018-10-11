# author: Xiang Gao @ Microsoft Research
# Oct 2018
from util import *
from collections import defaultdict


def cal_nist_bleu(path_refs, path_hyp, fld_out='temp', n_line=None):
	# call NIST script: mteval-v14c.pl
	# ftp://jaguar.ncsl.nist.gov/mt/resources/mteval-v14c.pl
	# you may need to cpan install XML:Twig Sort:Naturally String:Util 

	makedirs(fld_out)

	if n_line is None:
		n_line = len(open(path_hyp, encoding='utf-8').readlines())	
	_write_xml([''], fld_out + '/src.xml', 'src', n_line=n_line)
	_write_xml([path_hyp], fld_out + '/hyp.xml', 'hyp', n_line=n_line)
	_write_xml(path_refs, fld_out + '/ref.xml', 'ref', n_line=n_line)

	time.sleep(1)
	cmd = 'perl mteval-v14c.pl -s %s/src.xml -t %s/hyp.xml -r %s/ref.xml'%(fld_out, fld_out, fld_out)
	process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
	output, error = process.communicate()

	lines = output.decode().split('\n')
	try:
		nist = lines[-6].strip('\r').split()[1:5]
		bleu = lines[-4].strip('\r').split()[1:5]
	except Exception:
		print('mteval-v14c.pl returns unexpected message')
		print('cmd = '+cmd)
		print(output)
		print(error)
		exit()

	return [float(x) for x in nist], [float(x) for x in bleu]


def cal_cum_bleu(path_refs, path_hyp):
	# call Moses script: multi-bleu.pl
	# https://github.com/moses-smt/mosesdecoder/blob/master/scripts/generic/multi-bleu.perl
	# the 4-gram cum BLEU returned by this one should be very close to cal_nist_bleu
	# however multi-bleu.pl doesn't return cum BLEU of lower rank, so in nlp_metrics we preferr cal_nist_bleu
	# furthermore, this func doesn't support n_line argument

	process = subprocess.Popen(
			['perl', 'multi-bleu.perl'] + path_refs, 
			stdout=subprocess.PIPE, 
			stdin=subprocess.PIPE
			)
	with open(path_hyp, encoding='utf-8') as f:
		lines = f.readlines()
	for line in lines:
		process.stdin.write(line.encode())
	output, error = process.communicate()
	return output.decode()



def cal_entropy(path_hyp, n_line=None):
	# based on Yizhe Zhang's code

	etp_score = [0.0,0.0,0.0,0.0]
	counter = [defaultdict(int),defaultdict(int),defaultdict(int),defaultdict(int)]
	i = 0
	for line in open(path_hyp, encoding='utf-8'):
		i += 1
		words = line.strip('\n').split()
		for n in range(4):
			for idx in range(len(words)-n):
				ngram = ' '.join(words[idx:idx+n+1])
				counter[n][ngram] += 1
		if i == n_line:
			break

	for n in range(4):
		total = sum(counter[n].values())
		for v in counter[n].values():
			etp_score[n] += - v /total * (np.log(v) - np.log(total))

	return etp_score




def cal_len(path, n_line):
	l = []
	for line in open(path, encoding='utf8'):
		l.append(len(line.strip('\n').split()))
		if len(l) == n_line:
			break
	return np.mean(l)


def nlp_metrics(path_refs, path_hyp, fld_out='temp', n_line=None):
	nist, bleu = cal_nist_bleu(path_refs, path_hyp, fld_out, n_line)
	entropy = cal_entropy(path_hyp, n_line)
	avg_len = cal_len(path_hyp, n_line)
	return nist, bleu, entropy, avg_len




def _write_xml(paths_in, path_out, role, n_line=None):

	lines = [
		'<?xml version="1.0" encoding="UTF-8"?>',
		'<!DOCTYPE mteval SYSTEM "">',
		'<!-- generated by https://github.com/golsun/NLP-tools -->',
		'<!-- from: %s -->'%paths_in,
		'<!-- as inputs for ftp://jaguar.ncsl.nist.gov/mt/resources/mteval-v14c.pl -->',
		'<mteval>',
		]

	for i_in, path_in in enumerate(paths_in):

		# header ----

		if role == 'src':
			lines.append('<srcset setid="unnamed" srclang="src">')
			set_ending = '</srcset>'
		elif role == 'hyp':
			lines.append('<tstset setid="unnamed" srclang="src" trglang="tgt" sysid="unnamed">')
			set_ending = '</tstset>'
		elif role == 'ref':
			lines.append('<refset setid="unnamed" srclang="src" trglang="tgt" refid="ref%i">'%i_in)
			set_ending = '</refset>'
		
		lines.append('<doc docid="unnamed" genre="unnamed">')

		# body -----

		if role == 'src':
			body = [''] * n_line
		else:
			with open(path_in, 'r', encoding='utf-8') as f:
				body = f.readlines()
			if n_line is not None:
				body = body[:n_line]
		for i in range(len(body)):
			line = body[i].strip('\n')
			line = line.replace('&',' ').replace('<',' ')		# remove illegal xml char
			if len(line) == 0:
				line = '__empty__'
			lines.append('<p><seg id="%i"> %s </seg></p>'%(i + 1, line))

		# ending -----

		lines.append('</doc>')
		if role == 'src':
			lines.append('</srcset>')
		elif role == 'hyp':
			lines.append('</tstset>')
		elif role == 'ref':
			lines.append('</refset>')

	lines.append('</mteval>')
	with open(path_out, 'w', encoding='utf-8') as f:
		f.write(unicode('\n'.join(lines)))

