import dcnn_model
import dataUtil
import numpy as np
import data_queue
import tensorflow as tf
import time
import os

embed_dim = 60
num_of_layers = 2
top_k = 4
num_of_filters = [6, 14]
filter_size = [7, 5]
num_hidden = 100
num_class = 2
n_epochs = 20
batch_size = 1000
sentence_length = 119
dev_every = 100
checkpoint_every = 100
dev = 10000
num_checkpoints = 5

vocabulary_size = 680149

# Load data
#print("Loading data...")
x_dev, y_dev, x_test, y_test = data_queue.create_record(dev)     #create record and get dev data

sent = tf.placeholder(tf.int64, [None, sentence_length])
y = tf.placeholder(tf.float64, [None, num_class])
dropout_keep_prob = tf.placeholder(tf.float32, name="dropout")

with tf.name_scope("embedding_layer"):
    W = tf.Variable(tf.random_uniform([vocabulary_size, embed_dim], -1.0, 1.0), name="embed_W")
    sent_embed = tf.nn.embedding_lookup(W, sent)
    print("sent_embed:", sent_embed.shape)
    input_x = tf.expand_dims(sent_embed, -1)
    print("input_x:", input_x.shape)

W1 = tf.Variable(tf.truncated_normal([filter_size[0], embed_dim, 1, num_of_filters[0]], stddev=0.01), name="W1")
b1 = tf.Variable(tf.constant(0.1, shape=[num_of_filters[0], embed_dim]), "b1")

W2 = tf.Variable(tf.truncated_normal([filter_size[1], int(embed_dim/2), num_of_filters[0], num_of_filters[1]], stddev=0.01), name="W2")
b2 = tf.Variable(tf.constant(0.1, shape=[num_of_filters[1], embed_dim]), "b2")

Wh = tf.Variable(tf.truncated_normal([int(top_k*embed_dim*num_of_filters[1]/4), num_hidden]), "Wh")
bh = tf.Variable(tf.constant(0.1, shape=[num_hidden]), "bh")

Wo = tf.Variable(tf.truncated_normal([num_hidden, num_class]), "Wo")

model = dcnn_model.DCNN(batch_size, embed_dim, num_of_filters, top_k)
out = model.DCNN(input_x, W1, b1, W2, b2, Wh, bh, Wo, dropout_keep_prob)

with tf.name_scope("cost"):
    #cross_entropy+L2
    cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=out, labels=y)) + tf.contrib.layers.l2_regularizer(0.001)(W1) + tf.contrib.layers.l2_regularizer(0.001)(W2) + tf.contrib.layers.l2_regularizer(0.001)(Wo)

predict_op = tf.argmax(out, axis=1, name='predictions')
with tf.name_scope("accuracy"):
    acc = tf.reduce_mean(tf.cast(tf.equal(tf.argmax(y, 1), tf.argmax(out, 1)), tf.float32))



global_step = tf.Variable(0, name="global_step", trainable=False)
optimizer = tf.train.AdamOptimizer(1e-3)
grads_and_vars = optimizer.compute_gradients(cost)
train_op = optimizer.apply_gradients(grads_and_vars, global_step=global_step)

out_dir = os.path.abspath(os.path.join(os.path.curdir, "runs"))
print("Writing to {}\n".format(out_dir))

checkpoint_dir = os.path.abspath(os.path.join(out_dir, "checkpoints"))
checkpoint_prefix = os.path.join(checkpoint_dir, "model")
if not os.path.exists(checkpoint_dir):
    os.makedirs(checkpoint_dir)
saver = tf.train.Saver(tf.global_variables(), max_to_keep=num_checkpoints)
#load train data
filename = "train.tfrecords"
filename_queue = tf.train.string_input_producer([filename], num_epochs=None)
reader = tf.TFRecordReader()
key, value = reader.read(filename_queue)
features = tf.parse_single_example(value, features={'label': tf.FixedLenFeature([], tf.string), 'sent': tf.FixedLenFeature([], tf.string)})
sentence1 = tf.decode_raw(features["sent"], tf.int32)
label = tf.decode_raw(features["label"], tf.float64)
sentence = tf.reshape(sentence1, [sentence_length])
label = tf.reshape(label, [num_class])
sent_batch, label_batch = tf.train.shuffle_batch([sentence, label], batch_size=200, capacity=500, min_after_dequeue=0)

with tf.Session() as sess:
    print("get data")
    sess.run(tf.global_variables_initializer())
    sess.run(tf.local_variables_initializer())
    coord = tf.train.Coordinator()
    threads = tf.train.start_queue_runners(coord=coord)
    max_acc = 0
    best_at_step = 0
    print(sess.run(sentence1))
    print(sess.run(label))
    print("train...")
    for i in range(1000):
        x_batch, y_batch = sess.run([sent_batch, label_batch])
        feed_dict = {
        sent: x_batch,
        y: y_batch,
        dropout_keep_prob: 0.5
        }
        _, loss, accurarcy = sess.run([train_op, cost, acc], feed_dict)
        print("Train process  loss {:g}, acc {:g}".format(loss, accurarcy))
        current_step = tf.train.global_step(sess, global_step)
        if current_step % dev_every == 0:
            print("\nEvaluation:")
            feed_dict = {
                sent: x_dev,
                y: y_dev,
                dropout_keep_prob: 1.0
            }
            dev_loss, dev_accurarcy = sess.run([cost, acc], feed_dict)

            if dev_accurarcy >= max_acc:
                max_acc = dev_accurarcy
                best_at_step = current_step
                path = saver.save(sess, checkpoint_prefix, global_step=current_step)
                print("")

        if current_step % checkpoint_every == 0:
            print('Best of valid = {}, at step {}'.format(max_acc, best_at_step))

    coord.request_stop()
    coord.join(threads)

    saver.restore(sess, checkpoint_prefix + '-' + str(best_at_step))
    print("test...")
    feed_dict = {
       sent: x_test,
        y: y_test,
        dropout_keep_prob: 1.0
        }
    loss, accurarcy = sess.run([cost, acc], feed_dict)
    print("Test process  loss {:g}, acc {:g}".format(loss, accurarcy))









