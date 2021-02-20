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
	inVecEastbound = bloor_and_high_park + bloor_and_pacific + bloor_and_oakmount + bloor_and_mountview
	e = inVecEastbound 
	inVecWestbound = [e[6], e[7], e[4], e[5], e[2], e[3], e[0], e[1]]

def getRandomizedInVec(inVec_, randGen_):
	assert len(inVec_) == inVecLen
	r = inVec_.copy()
	#return r # tdr 
	for idx in [0, 1, 3, 4, 6, 7, 9, 10] if useHeadings else range(len(inVec_)):
		r[idx] += randGen.uniform(-0.0002, 0.0002)
	return r

def getNormalizedVal(val_, min_, max_):
	assert min_ < max_
	assert min_ < val_ < max_
	return (val_ - min_)/(max_ - min_)

def getNormalizedLat(lat_):
	latMin = 43.65106639812893
	latMax = 43.657971381468606
	return getNormalizedVal(lat_, latMin, latMax)

def getNormalizedLon(lon_):
	lonMin = -79.47340786040793
	lonMax = -79.45478260041482
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

outVecKeeleNorthOfBloor = [0., 0., 0., 0., 0., 1., 0., 0.]
outVecHighParkNorthOfBloor = [0., 1., 0., 0., 0., 0., 0., 0.]

trainInVecBatch = []
trainOutVecBatch = []
randGen = random.Random(37)
for iBatch in range(batchSz):
	if iBatch % 2 == 0:
		trainInVecBatch.append(getNormalizedInVec(getRandomizedInVec(inVecEastbound, randGen)))
		trainOutVecBatch.append(outVecKeeleNorthOfBloor)
	else:
		trainInVecBatch.append(getNormalizedInVec(getRandomizedInVec(inVecWestbound, randGen)))
		trainOutVecBatch.append(outVecHighParkNorthOfBloor)
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
		testInVecBatch.append(getNormalizedInVec(getRandomizedInVec(inVecEastbound, randGen)))
		testOutVecBatch.append(outVecKeeleNorthOfBloor)
	else:
		testInVecBatch.append(getNormalizedInVec(getRandomizedInVec(inVecWestbound, randGen)))
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
	r = np.argmax(outVec)
	return r

#print(tf.matmul(trainInVecBatch[0]*W))
#print(sess.run(W))
#print(sess.run(b))
#W_np = W.eval(session=sess)
#b_np = b.eval(session=sess)
for i in range(100):
	inVec = inVecWestbound if i % 2 == 0 else inVecEastbound
	for iAnswer in range(30):
		inVec = getRandomizedInVec(inVec, randGen)
	answer = runNN(inVec)
	print("%s" % answer)

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

