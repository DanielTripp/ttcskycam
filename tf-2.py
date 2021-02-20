#!/usr/bin/env python3

# =============================================================================
# Examples from Eugene Charniak's Introduction to Deep Learning 2018 MIT Press
# =============================================================================
 #CHAPTER 2 - #PG 48 - Using layers for the 1st time and adding saved checkpoints
import os, sys, random
import tensorflow as tf
import tensorflow.contrib.layers as layers
#from tensorflow.examples.tutorials.mnist import input_data
import numpy as np
import psycopg2

def file_to_string(filename_):
  with open(filename_) as fin:
    return fin.read()

PASSWORD = file_to_string(os.path.expanduser('~/.ttcskycam/DB_PASSWORD')).strip()

g_conn = None

def connect():
  global g_conn
  DATABASE_CONNECT_POSITIONAL_ARGS = ("dbname='postgres' user='dt' host='localhost' password='%s'" % PASSWORD,)
  DATABASE_CONNECT_KEYWORD_ARGS = {}
  g_conn = psycopg2.connect(*DATABASE_CONNECT_POSITIONAL_ARGS, **DATABASE_CONNECT_KEYWORD_ARGS)

def conn():
  if g_conn is None:
    connect()
  return g_conn

def vi_select_generator(croute_, end_time_em_, start_time_em_, dir_=None, include_unpredictables_=True, vid_=None, \
      forward_in_time_order_=False):
	# 2021: ignoring blank route 
	# 2021: including unpredictables 
	assert vid_ is None or len(vid_) > 0
	curs = (conn().cursor('cursor_%d' % (int(time.time()*1000))) if start_time_em_ == 0 else conn().cursor())
	dir_clause = ('and dir_tag like \'%%%%\\\\_%s\\\\_%%%%\' ' % (str(dir_)) if dir_ != None else ' ')
	#columns = '*'
	columns = ' graph_locs  '
	sql = 'select '+columns+' from ttc_vehicle_locations where '\
		+('route_tag = %s ')\
		+('' if include_unpredictables_ else ' and predictable = true ') \
		+' and time_retrieved <= %s and time_retrieved > %s '\
		+(' and vehicle_id = %s ' if vid_ else ' and vehicle_id != \'\' ') \
		+ dir_clause \
		+(' order by time' if forward_in_time_order_ else ' order by time desc')
	curs.execute(sql, [croute_, end_time_em_, start_time_em_] + ([vid_] if vid_ else []))
	while True:
		row = curs.fetchone()
		if not row:
			break
		#vi = vinfo.VehicleInfo.from_db(*row)
		yield row
	curs.close()

end_time_em = 1611929399123
for e in vi_select_generator('505', end_time_em, end_time_em - 1000*60*30):
	print(e)

sys.exit(1)


#Model:
# Pr(A(x))=softmax( relu( xU+Ub )V + Vb )
#if you have saved checkpoint

#mnist =  input_data.read_data_sets("MNIST_data/", one_hot=True)

batchSz=100

useHeadings = False
inVecLen = 12 if useHeadings else 8
outVecLen = 8

img=tf.placeholder(tf.float32,[batchSz,inVecLen])
ans=tf.placeholder(tf.float32,[batchSz,outVecLen])

fn=tf.nn.leaky_relu
num_layers = 3
assert num_layers >= 2
for i_layer in range(num_layers):
		if i_layer == 0:
				L1Output=layers.fully_connected(img,756,activation_fn=fn)
		elif i_layer < num_layers-1:
				L1Output=layers.fully_connected(L1Output,756,activation_fn=fn)
		elif i_layer == num_layers-1:
				prbs=layers.fully_connected(L1Output,outVecLen,tf.nn.softmax)
		else:
				assert False

#Cross entropy will be used for out loss function
xEnt=tf.reduce_mean(-tf.reduce_sum(ans*tf.log(prbs),reduction_indices=[1]))

#learning rate should be between 0.01-0.05
#train=tf.train.GradientDescentOptimizer(0.05).minimize(xEnt)
train=tf.train.AdamOptimizer(0.001).minimize(xEnt)
numCorrect=tf.equal(tf.argmax(prbs,1),tf.argmax(ans,1))
accuracy=tf.reduce_mean(tf.cast(numCorrect,tf.float32))

sess=tf.Session()
sess.run(tf.global_variables_initializer())

if useHeadings: 
	bloor_and_high_park = [43.65356343025547, -79.46519831703505, 80.]
	bloor_and_pacific = [43.65388980652754, -79.46368264797371, 80.]
	bloor_and_oakmount = [43.65417701617972, -79.4623293720261, 80.]
	bloor_and_mountview = [43.6545164439977, -79.46104827079571, 80.]
	#bloor_and_keele_eastbound = [43.65467164935167, -79.46000223849931, 80]
	bloor_east_of_keele = [43.65485460054855, -79.45924234384118]
	#bloor_and_keele_northbound = [43.65467164935167, -79.46000223849931, 350]
	keele_north_of_bloor = [43.65580161001621, -79.46042251584534]
	#full_eastbound = bloor_and_high_park + bloor_and_pacific + bloor_and_oakmount + bloor_and_mountview + bloor_and_keele_eastbound
	#full_northbound = bloor_and_high_park + bloor_and_pacific + bloor_and_oakmount + bloor_and_mountview + bloor_and_keele_northbound
	part = bloor_and_high_park + bloor_and_pacific + bloor_and_oakmount + bloor_and_mountview
else:
	bloor_and_high_park = [43.65356343025547, -79.46519831703505]
	bloor_and_pacific = [43.65388980652754, -79.46368264797371]
	bloor_and_oakmount = [43.65417701617972, -79.4623293720261]
	bloor_and_mountview = [43.6545164439977, -79.46104827079571]
	#bloor_and_keele_eastbound = [43.65467164935167, -79.46000223849931, 80]
	bloor_east_of_keele = [43.65485460054855, -79.45924234384118]
	#bloor_and_keele_northbound = [43.65467164935167, -79.46000223849931, 350]
	keele_north_of_bloor = [43.65580161001621, -79.46042251584534]
	#full_eastbound = bloor_and_high_park + bloor_and_pacific + bloor_and_oakmount + bloor_and_mountview + bloor_and_keele_eastbound
	#full_northbound = bloor_and_high_park + bloor_and_pacific + bloor_and_oakmount + bloor_and_mountview + bloor_and_keele_northbound
	inVecBloorAndHighParkEastbound = bloor_and_high_park + bloor_and_pacific + bloor_and_oakmount + bloor_and_mountview
	e = inVecBloorAndHighParkEastbound 
	inVecBloorAndHighParkWestbound = [e[6], e[7], e[4], e[5], e[2], e[3], e[0], e[1]]

inVecBloorEastboundTowardsDundas = [43.65534378441736, -79.45697817491998, 43.65567015101354, -79.45558881154923, 43.65590513386445, -79.45414531713804, 43.656286801869086, -79.45260911084067]

def getRandomizedInVec(inVec_, randGen_, numRandIterations_):
	assert len(inVec_) == inVecLen
	r = inVec_.copy()
	#return r # tdr 
	for iRandIteration in range(numRandIterations_):
		for idx in [0, 1, 3, 4, 6, 7, 9, 10] if useHeadings else range(len(inVec_)):
			r[idx] += randGen.uniform(-0.0002, 0.0002)
	return r

def getNormalizedVal(val_, min_, max_):
	assert min_ < max_
	assert min_ < val_ < max_
	return (val_ - min_)/(max_ - min_)

LONG_BRANCH = (43.58956722506657, -79.53955437311842)
BRICK_WORKS = (43.68619892890579, -79.3647991510632)

HAMILTON = (43.231817392963826, -79.8636528701807)
LINDSAY = (44.35094419471702, -78.73938493055135)

def getNormalizedLat(lat_):
	latMin = HAMILTON[0]
	latMax = LINDSAY[0]
	return getNormalizedVal(lat_, latMin, latMax)

def getNormalizedLon(lon_):
	lonMin = HAMILTON[1]
	lonMax = LINDSAY[1]
	return getNormalizedVal(lon_, lonMin, lonMax)

def getNormalizedInVec(inVec_):
	assert not useHeadings 
	r = []
	for idx, val in enumerate(inVec_):
		if idx % 2 == 0:
			r.append(getNormalizedLat(val))
		else:
			r.append(getNormalizedLon(val))
	return r

NUM_LINE_SEGMENTS = 8

def getOneHot(idx_):
	assert type(idx_) == int
	r = np.array(idx_).reshape(-1)
	r = np.eye(NUM_LINE_SEGMENTS)[r][0]
	return r

outVecKeeleNorthOfBloor = getOneHot(5)
outVecHighParkNorthOfBloor = getOneHot(1)
outVecBloorEastOfDundas = getOneHot(2)

trainInVecBatch = []
trainOutVecBatch = []
randGen = random.Random(37)
for iBatch in range(batchSz):
	if iBatch % 3 == 0:
		trainInVecBatch.append(getNormalizedInVec(getRandomizedInVec(inVecBloorAndHighParkEastbound, randGen, 1)))
		trainOutVecBatch.append(outVecKeeleNorthOfBloor)
	elif iBatch % 3 == 1:
		trainInVecBatch.append(getNormalizedInVec(getRandomizedInVec(inVecBloorAndHighParkWestbound, randGen, 1)))
		trainOutVecBatch.append(outVecHighParkNorthOfBloor)
	else:
		trainInVecBatch.append(getNormalizedInVec(getRandomizedInVec(inVecBloorEastboundTowardsDundas, randGen, 1)))
		trainOutVecBatch.append(outVecBloorEastOfDundas)
trainInVecBatch = np.array(trainInVecBatch)
trainOutVecBatch = np.array(trainOutVecBatch)

assert len(trainInVecBatch) == batchSz
assert len(trainInVecBatch[0]) == inVecLen
assert len(trainOutVecBatch) == batchSz
assert len(trainOutVecBatch[0]) == outVecLen

testInVecBatch = []
testOutVecBatch = []
randGen = random.Random(37)
for iBatch in range(batchSz):
	if iBatch % 2 == 0:
		testInVecBatch.append(getNormalizedInVec(getRandomizedInVec(inVecBloorAndHighParkEastbound, randGen, 1)))
		testOutVecBatch.append(outVecKeeleNorthOfBloor)
	else:
		testInVecBatch.append(getNormalizedInVec(getRandomizedInVec(inVecBloorAndHighParkWestbound, randGen, 1)))
		testOutVecBatch.append(outVecHighParkNorthOfBloor)
testInVecBatch = np.array(testInVecBatch)
testOutVecBatch = np.array(testOutVecBatch)

assert len(testInVecBatch) == batchSz
assert len(testInVecBatch[0]) == inVecLen
assert len(testOutVecBatch) == batchSz
assert len(testOutVecBatch[0]) == outVecLen

numEpochs=1000
#training loop
for iEpoch in range(numEpochs):
	trainAccuracy,_ = sess.run([accuracy, train], feed_dict={img: trainInVecBatch, ans: trainOutVecBatch}) 
	#print("epoch %d, train: %r" % (iEpoch, trainAccuracy))
	if iEpoch == 0 or iEpoch % 100 == 99:
		testAccuracy = sess.run(accuracy, feed_dict={img: testInVecBatch, ans: testOutVecBatch})
		#print("epoch %d, train: %.4f" % (iEpoch, trainAccuracy))
		print("epoch %d, train: %r, test: %r" % (iEpoch, trainAccuracy, testAccuracy))

def runNN(inVec_):
	inVec = getNormalizedInVec(inVec_)
	inVecBatch = np.array([inVec]*batchSz)
	outVecBatch = sess.run(prbs, feed_dict={img: inVecBatch})
	outVec = outVecBatch[0]
	r = int(np.argmax(outVec))
	return r

#print(tf.matmul(trainInVecBatch[0]*W))
#print(sess.run(W))
#print(sess.run(b))
#W_np = W.eval(session=sess)
#b_np = b.eval(session=sess)
for i in range(100):
	inVec = {0: inVecBloorAndHighParkWestbound, 1: inVecBloorAndHighParkEastbound, 2: inVecBloorEastboundTowardsDundas}[i % 3]
	inVec = getRandomizedInVec(inVec, randGen, 1)
	answer = runNN(inVec)
	correctAnswer = {0: 1, 1: 5, 2: 2}[i % 3]
	#print("%s" % answer)
	if answer != correctAnswer:
		print("%s %s" % (i % 3, answer == correctAnswer))

if 0:
	sumAcc=0
	for i in range(numEpochs):
		sumAcc += sess.run(xEnt,feed_dict={img: testInVecBatch, ans: testOutVecBatch})
	print("Test Accuracy: %r" % (sumAcc/numEpochs))

# can print a matrix that is an image, or a matrix of weights 
def print_matrix(matrix_, fmt_=".1f"):
	assert is_weights_for_one_digit(matrix_) or is_image_with_bias_pixel(matrix_) or is_image_without_bias_pixel(matrix_) \
		or is_unnormalized_image_with_bias_pixel(matrix_) or is_unnormalized_image_without_bias_pixel(matrix_)
	denormalize_image = True # tdr revert 
	if denormalize_image:
		fmt_ = "d"
		matrix_ = np.vectorize(lambda x: int(x*255))(matrix_)
	matrix = matrix_[:NUM_PIXELS]
	matrix = matrix.reshape(NUM_PIXELS_IN_EACH_DIMENSION, NUM_PIXELS_IN_EACH_DIMENSION)
	col_maxes = [max([len(("{:"+fmt_+"}").format(x)) for x in col]) for col in matrix.T]
	for x in matrix:
		for i, y in enumerate(x):
			print(("{:"+str(col_maxes[i])+fmt_+"}").format(y), end="  ")
		print("")
	if is_weights_for_one_digit(matrix_) or is_image_with_bias_pixel(matrix_) or is_unnormalized_image_with_bias_pixel(matrix_):
		print(matrix_[-1])

NUM_PIXELS = 784
assert NUM_PIXELS**0.5 % 1 == 0.0
NUM_PIXELS_IN_EACH_DIMENSION = int(NUM_PIXELS**0.5)
NUM_WEIGHTS_FOR_ONE_DIGIT = NUM_PIXELS + 1


def is_image_without_bias_pixel(matrix_):
	return matrix_.shape == (NUM_PIXELS,) and (matrix_.dtype == np.float64 or matrix_.dtype == np.float32)

def is_unnormalized_image_without_bias_pixel(matrix_):
	return matrix_.shape == (NUM_PIXELS,) and matrix_.dtype == np.uint8

def is_image_with_bias_pixel(matrix_):
	return matrix_.shape == (NUM_WEIGHTS_FOR_ONE_DIGIT,) and matrix_.dtype == np.float64

def is_unnormalized_image_with_bias_pixel(matrix_):
	return matrix_.shape == (NUM_WEIGHTS_FOR_ONE_DIGIT,) and matrix_.dtype == np.uint8

def is_weights_for_one_digit(matrix_):
	return matrix_.shape == (NUM_WEIGHTS_FOR_ONE_DIGIT,) and matrix_.dtype == np.float64



