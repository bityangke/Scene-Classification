import keras
import tensorflow as tf
from keras.callbacks import ModelCheckpoint, EarlyStopping
from keras.callbacks import ReduceLROnPlateau
from keras.optimizers import SGD
from keras.preprocessing.image import ImageDataGenerator
from keras.utils import multi_gpu_model

from resnet_152 import resnet152_model
from utils import get_available_gpus, get_available_cpus

if __name__ == '__main__':
    img_width, img_height = 320, 320
    num_channels = 3
    train_data = 'data/train'
    valid_data = 'data/valid'
    num_classes = 80
    num_train_samples = 53879
    num_valid_samples = 7120
    verbose = 1
    batch_size = 12
    num_epochs = 10
    patience = 50

    # prepare data augmentation configuration
    train_data_gen = ImageDataGenerator(rotation_range=20.,
                                        width_shift_range=0.1,
                                        height_shift_range=0.1,
                                        zoom_range=0.2,
                                        horizontal_flip=True)
    valid_data_gen = ImageDataGenerator()

    # generators
    train_generator = train_data_gen.flow_from_directory(train_data, (img_width, img_height), batch_size=batch_size,
                                                         class_mode='categorical', shuffle=True)
    valid_generator = valid_data_gen.flow_from_directory(valid_data, (img_width, img_height), batch_size=batch_size,
                                                         class_mode='categorical', shuffle=True)


    class MyCbk(keras.callbacks.Callback):
        def __init__(self, model):
            keras.callbacks.Callback.__init__(self)
            self.model_to_save = model

        def on_epoch_end(self, epoch, logs=None):
            fmt = 'models/model.%02d-%.4f.hdf5'
            self.model_to_save.save(fmt % (epoch, logs['val_acc']))


    # Callbacks
    tensor_board = keras.callbacks.TensorBoard(log_dir='./logs', histogram_freq=0, write_graph=True, write_images=True)
    early_stop = EarlyStopping('val_acc', patience=patience)
    reduce_lr = ReduceLROnPlateau('val_acc', factor=0.1, patience=int(patience / 4), verbose=1)
    trained_models_path = 'models/model'
    model_names = trained_models_path + '.{epoch:02d}-{val_acc:.4f}.hdf5'
    model_checkpoint = ModelCheckpoint(model_names, monitor='val_acc', verbose=1, save_best_only=True)

    num_gpu = len(get_available_gpus())
    if num_gpu >= 2:
        with tf.device("/cpu:0"):
            model = resnet152_model(img_rows=img_height, img_cols=img_width, color_type=num_channels,
                                    num_classes=num_classes)

        new_model = multi_gpu_model(model, gpus=num_gpu)
        # rewrite the callback: saving through the original model and not the multi-gpu model.
        model_checkpoint = MyCbk(model)
    else:
        new_model = resnet152_model(img_rows=img_height, img_cols=img_width, color_type=num_channels,
                                num_classes=num_classes)

    sgd = SGD(lr=1e-3, decay=1e-6, momentum=0.9, nesterov=True)
    new_model.compile(optimizer=sgd, loss='categorical_crossentropy', metrics=['accuracy'])

    callbacks = [tensor_board, model_checkpoint, early_stop, reduce_lr]


    # fine tune the model
    new_model.fit_generator(
        train_generator,
        steps_per_epoch=num_train_samples / batch_size,
        validation_data=valid_generator,
        validation_steps=num_valid_samples / batch_size,
        shuffle=True,
        epochs=num_epochs,
        callbacks=callbacks,
        verbose=verbose,
        use_multiprocessing=True,
        workers=2)

