import logging
import keras
import keras.backend as K
from keras_text_cls.model import BaseModel
from keras_text_cls.model.utils import init_embedding_layer
from keras.layers import Dense, Flatten, Dropout, Conv1D, MaxPooling1D, LSTM, Lambda, concatenate


class TextRCNN(BaseModel):
    """
    Text RCNN Model constructs recurrent convolutional neutral networks for text classification

    More details about HAN can be found in paper:
    <a href="https://www.aaai.org/ocs/index.php/AAAI/AAAI15/paper/download/9745/9552">Recurrent Convolutional Neural Networks for Text Classification</a>

    Attributes
    ----------
    num_classes: int
        the number of classes
    embedding_dim: int
        the dimension of embedding vector, default is 128
    embedding_matrix: 2d np.array
        pre-trained embedding matrix is an array of embedding vector,
            where index 0 must be reserved for SYMBOL_PADDING, index 1 must be reserved for SYMBOL_UNKNOWN
        default is None
    embedding_trainable: bool
        Is the embedding layer trainable in the network. It must be set to True, when embedding matrix is None.
        Default is False.
        Set False if embedding matrix is pre-trained and set in the model
    embedding_vocab_size: int
        the vocabulary size for embedding.
        Default is None, which indicates the size is equal to the length of embedding matrix
        embedding_vocab_size must be set to initialize the size of the embedding layer, when embedding_matrix=None
    rnn_hidden_units: int
        the number of rnn hidden units, default is 100
    conv_hidden_units: int
        the number of conv hidden units, default is 100
    pooling_strategy: str,
         pooling strategy for word sequences, either "REDUCE_MEAN" or "REDUCE_MAX"
    max_seq_len: int
        maximum length of words for each text, longer text will be truncated more than max_seq_len,
        shorter text will be padded
    num_hidden_units: integer array
        an array of positive integers, indicating the number of units for each hidden layer, default is []
    hidden_activation: str
        activation function of neutral unit, default is "relu"
    dropout: float (0,1)
        dropout rate, must be equal or greater than 0 and equal or less than 1, default is 0.5
    multi_label: bool
        is the labels are multi-label classification, default is True
    """
    def __init__(self, num_classes,
                 embedding_dim=128, embedding_matrix=None, embedding_trainable=False, embedding_vocab_size=None,
                 rnn_hidden_units=100, conv_hidden_units=100,
                 pooling_strategy="REDUCE_MAX", max_seq_len=300,
                 num_hidden_units=[100], hidden_activation="relu",
                 dropout=0.5, multi_label=True):
        super(TextRCNN, self).__init__(name='TextRCNN')
        self.num_classes = num_classes
        self.embedding_dim = embedding_dim
        self.embedding_matrix = embedding_matrix
        self.embedding_trainable = embedding_trainable
        self.pooling_strategy = pooling_strategy
        self.max_seq_len = max_seq_len
        self.num_hidden_units = num_hidden_units
        self.hidden_activation = hidden_activation
        self.dropout = dropout
        self.multi_label = multi_label
        self.rnn_hidden_units = rnn_hidden_units

        layer_input = keras.layers.Input(shape=(self.max_seq_len,), dtype='int32')

        # embedding layer
        layer_embedding = init_embedding_layer(embedding_matrix, embedding_dim, embedding_vocab_size,
                                               embedding_trainable, max_seq_len)

        layer_lstm_forward = LSTM(rnn_hidden_units, return_sequences=True)
        layer_lstm_backward = LSTM(rnn_hidden_units, return_sequences=True, go_backwards=True)
        # output of layer_lstm_backward was in reversed order
        layer_reverse = Lambda(lambda x: K.reverse(x, axes=1))

        layer_conv = Conv1D(conv_hidden_units, kernel_size=1, activation="tanh")
        layer_max_pool = Lambda(lambda x: K.max(x, axis=1))

        # hidden layer
        layer_hiddens = []
        prev_input_dim = embedding_dim
        for n in num_hidden_units:
            layer_hiddens.append(
                Dense(n, input_dim=prev_input_dim, activation=hidden_activation)
            )
            if dropout > 0:
                layer_hiddens.append(Dropout(dropout))
            prev_input_dim = n

        if multi_label:
            output_activation = "sigmoid"
        else:
            output_activation = "softmax"
        # output layer
        layer_output = keras.layers.Dense(num_classes, activation=output_activation)

        input = layer_input
        x = layer_embedding(input)
        forward = layer_lstm_forward(x)
        backward = layer_lstm_backward(x)
        backward = layer_reverse(backward)
        together = concatenate([forward, x, backward], axis=2)
        semantic = layer_conv(together)
        x = layer_max_pool(semantic)

        for hidden in layer_hiddens:
            x = hidden(x)
        output = layer_output(x)

        self.model = keras.Model(input, output)

    def call(self, inputs):
        """
        :param inputs: 2-dim np.array, the element is the word index
        :return: predicted class probabilities
        """
        assert len(inputs.shape) == 2
        return self.model(inputs)
