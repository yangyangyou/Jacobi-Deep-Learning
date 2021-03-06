import datetime
import tensorflow as tf
import numpy as np
import time as tm
import math
import sys
import pickle as pkl
import matplotlib.pyplot as plt
from numpy import *
###start here
"""
Parameters
K - size of x
N - size of y
snrdb_low - the lower bound of noise db used during training
snr_high - the higher bound of noise db used during training
L - number of layers in DetNet
v_size = size of auxiliary variable at each layer
hl_size - size of hidden layer at each DetNet layer (the dimention the layers input are increased to
startingLearningRate - the initial step size of the gradient descent algorithm#本文展开的是梯度下降算法
decay_factor & decay_step_size - each decay_step_size steps the learning rate decay by decay_factor
train_iter - number of train iterations
train_batch_size - batch size during training phase
test_iter - number of test iterations
test_batch_size  - batch size during testing phase
LOG_LOSS - equal 1 if loss of each layer should be sumed in proportion to the layer depth, otherwise all losses have the same weight 
res_alpha- the proportion of the previuos layer output to be added to the current layers output (view ResNet article)
snrdb_low_test & snrdb_high_test & num_snr - when testing, num_snr different SNR values will be tested, uniformly spread between snrdb_low_test and snrdb_high_test 
"""
#本文展开的是梯度下降算法

sess = tf.InteractiveSession()#能让你在运行图的时候，插入一些计算图，这些计算图是由某些操作(operations)构成的
tic = tm.time()
global_tic=tm.time()
# parameters
K = 16
N = 64
L = 10 #层数
snrdb_low = 0 #信噪比
snrdb_high = 20
snr_low = 10.0 ** (snrdb_low / 10.0)#最小的信噪比化为十进制
snr_high = 10.0 ** (snrdb_high / 10.0)
v_size = 2 * K#每层辅助变量的大小
hl_size =  K  #隐藏层的大小
startingLearningRate = 0.0001#初始学习率
decay_factor = 0.97
decay_step_size = 50000
train_iter = 50000 #训练迭代次数
train_batch_size = 10000#批量大小
test_iter = 5000
test_batch_size = 3000
LOG_LOSS = 1#残差网络-每一层的损失应按层深的比例计算
res_alpha = 0.9#要添加到当前层输出的之前层输出的 比例
num_snr = 21#要添加到当前层输出的之前层输出的 比例
snrdb_low_test = 0
snrdb_high_test = 20

"""Data generation for train and test phases
In this example, both functions are the same.
This duplication is in order to easily allow testing cases where the test is over different distributions of data than in the training phase.
e.g. training over gaussian i.i.d. channels and testing over a specific constant channel.
currently both test and train are over i.i.d gaussian channel.
"""
nowTime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 现在
print("K=", K, "N=", N, "L=", L, "train_iter=", train_iter, "now=", nowTime)


#定义各种数据，备以调用
def generate_data_iid_test(B, K, N, snr_low, snr_high):#B为train_batch_size批次数5000
    H_ = np.random.randn(B, N, K) #从标准正态分布中随机取值 #B组N*K维随机值(小数点后八位)
   # W_ = np.zeros([B, K, K])
    x_ = np.sign(np.random.rand(B, K) - 0.5)#-0.5到0.5区间的随机值  变成B*K维数值为1或-1的矩阵
    #The sign function returns -1 if x < 0, 0 if x==0, 1 if x > 0.
    y_ = np.zeros([B, N]) #接受向量
    w = np.random.randn(B, N)#噪声
    Hy_ = np.zeros([B, K])#x_ * 0#零矩阵
    H2  = np.zeros([B, K, K])
    HH_ = np.zeros([B, K, K])
    SNR_ = np.zeros([B])#B*1组
    for i in range(B):
        SNR = np.random.uniform(low=snr_low, high=snr_high)
        H = H_[i, :, :]
        tmp_snr = (H.T.dot(H)).trace() / K  #H转置乘以H  求对角元素的和再除以K
        H = H / np.sqrt(tmp_snr) * np.sqrt(SNR)   #压缩了一下
        H_[i, :, :] = H  #信道矩阵
        y_[i, :] = (H.dot(x_[i, :]) + w[i, :]) #y_=Hx_+w
        #充分压缩统计量
        Hy_[i, :] = H.T.dot(y_[i, :])          #Hy_=H转置*y_
        HH_[i, :, :] = H.T.dot(H_[i, :, :])    #HH_=H转置*H_
        SNR_[i] = SNR
        H2[i, :, :]=np.diag(np.diag(HH_[i, :, :]))
    return y_, H2, Hy_, HH_, x_, SNR_
#除了x为整数组成的矩阵，其余都是小数点后八位的小数组成的矩阵

def generate_data_train(B, K, N, snr_low, snr_high):#和上一段完全一样，可以合并
    H_ = np.random.randn(B, N, K)
    x_ = np.sign(np.random.rand(B, K) - 0.5)
    #A= tf.matrix_inverse(HH)
    #x_ =A*y_
    y_ = np.zeros([B, N])
    w = np.random.randn(B, N)
    Hy_ = x_ * 0
    HH_ = np.zeros([B, K, K])
    H2  = np.zeros([B, K, K])
    SNR_ = np.zeros([B])
    for i in range(B):
        SNR = np.random.uniform(low=snr_low, high=snr_high)
        H = H_[i, :, :]
        tmp_snr = (H.T.dot(H)).trace() / K
        H = H / np.sqrt(tmp_snr) * np.sqrt(SNR)
        H_[i, :, :] = H
        y_[i, :] = (H.dot(x_[i, :]) + w[i, :])
        Hy_[i, :] = H.T.dot(y_[i, :])
        HH_[i, :, :] = H.T.dot(H_[i, :, :])
        SNR_[i] = SNR
        H2[i, :, :]=np.diag(np.diag(HH_[i, :, :]))
    return y_, H2, Hy_, HH_, x_, SNR_


def piecewise_linear_soft_sign(x):
    t = tf.Variable(0.1)
    y = -1 + tf.nn.relu(x + t) / (tf.abs(t) + 0.00001) - tf.nn.relu(x - t) / (tf.abs(t) + 0.00001)
    return y#max(0,)relu函数是小于零都为零，大于零的数不变;abs为绝对值


def affine_layer(x, input_size, output_size, Layer_num):
    W = tf.Variable(tf.random_normal([input_size, output_size], stddev=0.1))#随机取input*output维的标准差为0.01的矩阵
    w = tf.Variable(tf.random_normal([1, output_size], stddev=0.1))
    y = tf.matmul(x, W)+w
    return y


def relu_layer(x, input_size, output_size, Layer_num):
    y = tf.nn.relu(affine_layer(x, input_size, output_size, Layer_num))#relu只保留正值
    return y


def sign_layer(x, input_size, output_size, Layer_num):#输出层，输出-1或-1 ，从而和输入值作比较求误码率
    y = piecewise_linear_soft_sign(affine_layer(x, input_size, output_size, Layer_num))
    return y


# tensorflow placeholders（占位符：先定义不赋值后面通过feed_dict以字典的方式填充占位）, 为训练和测试网络而给模型的输入

HY = tf.placeholder(tf.float32, shape=[None, K])#tf.placeholder（数值类型，一行K列，名字）#H转置*y
X = tf.placeholder(tf.float32, shape=[None, K])
HH = tf.placeholder(tf.float32, shape=[None, K, K])
HT = tf.placeholder(tf.float32, shape=[None, K, K])
batch_size = tf.shape(HY)[0]#shape（）括号里的形状用矩阵表示
B=HH-HT
C=-tf.matmul(tf.matrix_inverse(HT),B)
#MMSE算法
#tf.expand_dim:维度增加一维，可以使用tf.expand_dims(input, dim, name=None)函数
X_LS = tf.matmul(tf.expand_dims(HY, 1), tf.matrix_inverse(HH)) #X=HH的逆*y？#加一维下面又减一维都是为了实现矩阵运算
X_LS = tf.squeeze(X_LS, 1)#删除所有大小是1的维度
loss_LS = tf.reduce_mean(tf.square(X - X_LS))#损失函数军方误差
ber_LS = tf.reduce_mean(tf.cast(tf.not_equal(X, tf.sign(X_LS)), tf.float32))#MMSE算法 sign相当于解调
# tf.reduce_mean函数用于计算张量tensor沿着指定的数轴（tensor的某一维度）上的的平均值，主要用作降维或者计算tensor（图像）的平均值。

#153-180行为了计算神经网络的误码率
S = []#对输入x的评估
S.append(tf.zeros([batch_size, K]))#append函数  S的末尾加上（）的内容#1*K=40
V = []#辅助变量
V.append(tf.zeros([batch_size, v_size]))#1*K
LOSS = []  # 每一层的代价函数
LOSS.append(tf.zeros([]))
BER = []
BER.append(tf.zeros([]))

# The architecture of DetNet
#D=np.diag(np.diag(HH))

#D_inv = np.linalg.inv(A)
#assert(np.dot(D, D_inv).all() == (np.eye(2)).all())
#C=-tf.matmul(tf.matrix_inverse(D),B )

for i in range(1, L):#L为神经网络层数
    
    #temp1 = tf.matmul(tf.expand_dims(S[-1], 1), HH)#matmul矩阵相乘，multiply是对应元素相乘；tf.expand_dims将全1插进S[]的第二列
    #(B,K)维加一维变成（B，1，K）,在通过squeeze变回(B,K)维。为了使S【】可以和HH相乘
 
    #temp1 = tf.squeeze(temp1, 1)#temp1中是1的全删除
    S[-1] = tf.squeeze(S[-1], 1)
    #temp1 = tf.matmul(C, temp1)+tf.matmul(tf.matrix_inverse(D),HY)
    #temp1 = tf.matmul(B,temp1)+HY*1/N
    #Z = tf.concat([HY, S[-1], temp1], 1)#concat把五个（假如用户数40）40*1矩阵拼在一起,200*1的矩阵
    
    ZZ = relu_layer(S[-1], K , hl_size, 'relu' + str(i))#str(i）是1到L的区间#320=200+3*40.#就是论文里面的Zk #max(0,)relu函数是小于零都为零，大于零的数不变;abs为绝对值
    S.append(sign_layer(ZZ, hl_size, K, 'sign' + str(i)))#120行定义的；分别对应(x, input_size, output_size, Layer_num)
   
    #S[-1] =C.dot(S[-1])
    # tf.matrix_inverse(np.diag(np.diag(HY)))*(HY-np.diag(np.diag(HY)))*S[-1]
    S[i] = (1 - res_alpha) * S[i] + res_alpha * S[i - 1]#0.1*S【i】+0.9*S【i-1】#S是各层对输入的评估#残余特征保留
    #V.append(affine_layer(ZZ, hl_size, v_size, 'aff' + str(i)))#分别对应(x, input_size, output_size, Layer_num)
    #V[i] = (1 - res_alpha) * V[i] + res_alpha * V[i - 1]
    if LOG_LOSS == 1:#残差网络-每一层的损失应按层深的比例计算
        LOSS.append(np.log(i) * tf.reduce_mean(tf.reduce_mean(tf.square(X - S[-1]), 1)))#tf.reduce_mean 函数用于计算张量tensor沿着指定的数轴（tensor的某一维度）上的的平均值，主要用作降维或者计算tensor（图像）的平均值。
         #tf.reduce_mean(tf.square(X - S[-1]), 1) / tf.reduce_mean(tf.square(X - X_LS), 1)))#为什么有个除法？
    else:
        LOSS.append(tf.reduce_mean(tf.reduce_mean(tf.square(X - S[-1]), 1)))#tf.reduce_mean(X-S,1)，1是按列求均值，第二个再求一次均值。
    BER.append(tf.reduce_mean(tf.cast(tf.not_equal(X, tf.sign(S[-1])), tf.float32)))
#The sign function returns -1 if x < 0, 0 if x==0, 1 if x > 0.
TOTAL_LOSS = tf.add_n(LOSS)
#global_step在滑动平均、优化器、指数衰减学习率等方面都有用到，这个变量的实际意义非常好理解：
#代表全局步数，比如在多少步该进行什么操作，现在神经网络训练到多少轮等等，类似于一个钟表。
global_step = tf.Variable(0, trainable=False)
learning_rate = tf.train.exponential_decay(startingLearningRate, global_step, decay_step_size, decay_factor,
                                           staircase=True)#学习率
train_step = tf.train.AdamOptimizer(learning_rate).minimize(TOTAL_LOSS)#训练目标
#tf.Variable定义的变量是tf自定义的数据结构，以张量形式存在于网络当中。这也是w, b以及global_steps能被后台改变的原因。
#上面那个问题也是这个原因，global_steps在右边，但它不是简单的value，而是特殊的数据结构(tensorflow框架使然)。
#AdamOptimizer是一个寻找全局最优点的优化算法，引入了二次方梯度校正。相比于基础SGD算法，1.不容易陷于局部优点。2.速度更快

# 变量运行前必须做初始化操作
init_op = tf.global_variables_initializer()
sess.run(init_op)


# Training DetNet
for i in range(train_iter):  # num of train iter
    #y_,      H_,     Hy_,        HH_,      x_,    SNR_                                B,       K, N, snr_low, snr_high
    batch_Y, batch_H, batch_HY, batch_HH, batch_X, SNR1 = generate_data_train(train_batch_size, K, N, snr_low, snr_high)
    train_step.run(feed_dict={HY: batch_HY, HH: batch_HH, X: batch_X, HT: batch_H})#用feed_dict以字典的方式填充上面定义但没有赋值的占位符
    if i % 100 == 0:#i能否被100整除 为了实时观察结构
        batch_Y, batch_H, batch_HY, batch_HH, batch_X, SNR1 = generate_data_iid_test(train_batch_size, K, N, snr_low, snr_high)
        results = sess.run([ber_LS, ber_J,BER[L - 1]], {HY: batch_HY, HH: batch_HH, X: batch_X, HT: batch_H})
        print_string = [i] + results
        print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "|", ' '.join('%s' % x for x in print_string))
       # print(ber_LS)
        
# Testing the trained model
snrdb_list = np.linspace(snrdb_low_test, snrdb_high_test, num_snr)#np.linspace等差数列函数
snr_list = 10.0 ** (snrdb_list / 10.0)  #**表示次方的意思
bers = np.zeros((1, num_snr))#定义各个信噪比下深度学习的误码率
berss = np.zeros((1, num_snr))#定义信噪比下MMSE的误码率
bersss = np.zeros((1, num_snr))
times = np.zeros((1, num_snr))#定义信噪比下花费时间
tmp_bers = np.zeros((1, test_iter))#定义每次迭代下深度学习的误码率
tmp_berss = np.zeros((1, test_iter))#定义每次迭代下MMSE的误码率
tmp_bersss = np.zeros((1, test_iter))
tmp_times = np.zeros((1, test_iter))#定义每次迭代下花费的时间
for j in range(num_snr):#信噪比大循环
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "|", 'snr=', snrdb_list[j])
    for jj in range(test_iter):#迭代小循环
        batch_Y, batch_H, batch_HY, batch_HH, batch_X, SNR1 = generate_data_iid_test(test_batch_size, K, N, snr_list[j],
                                                                                     snr_list[j])
        tic = tm.time()
        tmp_bers[:, jj] = np.array(sess.run( BER[L - 1], {HY: batch_HY, HH: batch_HH, X: batch_X, HT: batch_H}))
        tmp_berss[:, jj] = np.array(sess.run( ber_LS, {HY: batch_HY, HH: batch_HH, X: batch_X, HT: batch_H}))
        tmp_bersss[:, jj] = np.array(sess.run( ber_J, {HY: batch_HY, HH: batch_HH, X: batch_X, HT: batch_H}))
        toc = tm.time()
        tmp_times[0][jj] = toc - tic
    
    bers[0][j] = np.mean(tmp_bers, 1)
    berss[0][j] = np.mean(tmp_berss, 1)
    bersss[0][j] = np.mean(tmp_bersss, 1)
    times[0][j] = np.mean(tmp_times[0]) / test_batch_size

print('snrdb_list')
print(snrdb_list)
print('berss')
print(berss)
print('bersss')
print(bersss)
print('bers')
print(bers)
print('times')
print(times)
global_toc=tm.time()
print("total coat time: ",global_toc-global_tic)

snrdb_list = mat([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20])
print(snrdb_list.shape)
plt.plot(snrdb_list, berss, marker='o', mec='g', mfc='w')#,label='MMSE') 
plt.plot(snrdb_list, bersss,  marker='*', mec='b')#, label='J')
plt.plot(snrdb_list, bers, 'rs')#,label='J-net')
plt.yscale('log')
plt.xlabel('SNR')
plt.ylabel('BER')

#plt.xticks(x, names, rotation=1)
 
#plt.margins(0)
#plt.subplots_adjust(bottom=0.10)

plt.grid()
plt.legend('MMSE','J','J-Net')#loc='upper right',ncol = 1)
#plt.savefig('DL_Detection_IM_BER_matplotlib')
plt.show()
