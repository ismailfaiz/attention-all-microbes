import os
import scipy
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import sklearn
# from tensorboard.plugins import projector
from amplicon_gpt.losses import _pairwise_distances
from skbio.stats.distance import DistanceMatrix
import skbio.stats.ordination
from unifrac import unweighted
from biom import load_table


def mean_confidence_interval(data, confidence=0.95):
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), scipy.stats.sem(a)
    h = se * scipy.stats.t.ppf((1 + confidence) / 2., n-1)
    return m, h


def mean_absolute_error(dataset, model, fname, s_type):
    pred_age = tf.squeeze(model.predict(dataset)).numpy()
    true_age = np.concatenate([tf.squeeze(ys).numpy() for (_, ys) in dataset])
    mae, h = mean_confidence_interval(np.abs(true_age - pred_age))

    min_x = 15
    max_x = np.max(true_age) + 2
    coeff = np.polyfit(true_age, pred_age, deg=1)
    p = np.poly1d(coeff)
    xx = np.linspace(min_x, max_x, 1000)
    yy = p(xx)

    plt.figure(figsize=(4, 4))
    plt.rcParams.update({
        'text.usetex': True
    })
    plt.subplot(1, 1, 1)
    plt.scatter(true_age, pred_age, 7, marker='.', c='grey', alpha=0.5)
    plt.plot(xx, yy)
    # plt.xlim(min_x,max_x)
    # plt.ylim(min_x,max_x)
    mae, h = '%.4g' % mae, '%.4g' % h
    plt.xlabel('Reported age')
    plt.ylabel('Predicted age')
    plt.title(rf"""{s_type} microbiota
              MAE: ${mae} \pm {h}$""")
    plt.savefig(fname)
    plt.close()


class BaseCheckpoint(tf.keras.callbacks.Callback):
    def __init__(self, root_path, dataset, s_type, steps_per_checkpoint=5,
                 **kwargs):
        super().__init__()

        self.dataset = dataset
        self.root_path = root_path
        self.model_path = os.path.join(self.root_path, 'model.keras')
        self.figure_path = os.path.join(self.root_path, 'figures')
        self.cur_step = 1
        self.total_mae = 0
        self.s_type = s_type
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        if not os.path.exists(self.figure_path):
            os.makedirs(self.figure_path)


class MAE_Scatter(tf.keras.callbacks.Callback):
    def __init__(self, root_path, dataset, s_type, title,
                 steps_per_checkpoint=5, **kwargs):
        super().__init__()
        self.dataset = dataset
        self.root_path = root_path
        self.model_path = os.path.join(self.root_path, 'model.keras')
        self.figure_path = os.path.join(self.root_path, 'figures')
        self.cur_step = 0
        self.total_mae = 0
        self.s_type = s_type
        self.title = title
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        if not os.path.exists(self.figure_path):
            os.makedirs(self.figure_path)

    def on_epoch_end(self, epoch, logs=None):
        if self.cur_step % 5 == 0:
            self.total_mae += 1
            self.model.save(self.model_path, save_format='keras')
            mean_absolute_error(
                self.dataset,
                self.model,
                fname=os.path.join(
                    self.figure_path, f'MAE-{self.title}-{self.total_mae}.png'
                    ),
                s_type=self.s_type
            )
            self.cur_step = 0
        self.cur_step += 1
        return super().on_epoch_end(epoch, logs)


class ProjectEncoder(tf.keras.callbacks.Callback):
    def __init__(self, data, model_path, pred_pcoa_path, true_pcoa_path,
                 table_path, tree_path, num_samples, batch_size, **kwargs):
        super().__init__()
        self.batch_size = batch_size
        self.data = data
        self.table = load_table(table_path)
        self.model_path = model_path
        self.cur_step = 0
        self.pred_pcoa_path = pred_pcoa_path
        self.true_pcoa_path = true_pcoa_path
        self.table_path = table_path
        self.tree_path = tree_path
        self.num_samples = num_samples

    def _log_epoch_data(self):
        tf.print('loggin data...')
        self.model.save(os.path.join(self.model_path, 'encoder.keras'),
                        save_format='keras')
        total_samples = (int(self.table.shape[1] / self.batch_size)
                         * self.batch_size)

        sample_indices = np.arange(total_samples)
        np.random.shuffle(sample_indices)
        sample_indices = sample_indices[:self.num_samples]
        pred = self.model.predict(self.data)

        pred = tf.gather(pred, sample_indices)
        distances = _pairwise_distances(pred, squared=False)
        pred_unifrac_distances = DistanceMatrix(
            distances.numpy(),
            self.table.ids(axis='sample')[sample_indices],
            validate=False
        )
        pred_pcoa = skbio.stats.ordination.pcoa(pred_unifrac_distances,
                                                method='fsvd',
                                                number_of_dimensions=3,
                                                inplace=True)
        pred_pcoa.write(self.pred_pcoa_path)

        true_unifrac_distances = unweighted(
                self.table_path, self.tree_path
                ).filter(self.table.ids(axis='sample')[sample_indices])
        true_pcoa = skbio.stats.ordination.pcoa(true_unifrac_distances,
                                                method='fsvd',
                                                number_of_dimensions=3,
                                                inplace=True)
        true_pcoa.write(self.true_pcoa_path)

    def on_epoch_end(self, epoch, logs=None):
        if self.cur_step % 5 == 0:
            self._log_epoch_data()
            self.cur_step = 0
        self.cur_step += 1


class Accuracy(tf.keras.callbacks.Callback):
    def __init__(self, root_path, dataset, s_type, steps_per_checkpoint=5,
                 **kwargs):
        super().__init__()
        self.dataset = dataset
        self.root_path = root_path
        self.model_path = os.path.join(self.root_path, 'model.keras')
        self.figure_path = os.path.join(self.root_path, 'figures')
        self.cur_step = 0
        self.total_mae = 0
        self.s_type = s_type
        self.steps_per_checkpoint = steps_per_checkpoint
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        if not os.path.exists(self.figure_path):
            os.makedirs(self.figure_path)

    def on_epoch_end(self, epoch, logs=None):
        if self.cur_step % self.steps_per_checkpoint == 0:
            self.total_mae += 1
            self.model.save(self.model_path, save_format='keras')

            pred_cat = tf.squeeze(self.model.predict(self.dataset)).numpy()
            true_cat = np.concatenate([tf.squeeze(ys).numpy() for (_, ys) in
                                       self.dataset])

            def plot_prc(name, labels, predictions, **kwargs):
                precision, recall, _ = sklearn.metrics.precision_recall_curve(
                    labels,
                    predictions
                )

                plt.plot(precision, recall, label=name, linewidth=2, **kwargs)
                plt.xlabel('Precision')
                plt.ylabel('Recall')
                plt.grid(True)
                ax = plt.gca()
                ax.set_aspect('equal')
                fname = os.path.join(self.figure_path,
                                     f'auc-{self.total_mae}.png')
                plt.savefig(fname)
                plt.close('all')

            plot_prc('AUC', true_cat, pred_cat)

            def plot_roc(name, labels, predictions, **kwargs):
                fp, tp, _ = sklearn.metrics.roc_curve(labels, predictions)

                plt.plot(100*fp, 100*tp, label=name, linewidth=2, **kwargs)
                plt.xlabel('False positives [%]')
                plt.ylabel('True positives [%]')
                plt.xlim([-0.5, 20])
                plt.ylim([80, 100.5])
                plt.grid(True)
                ax = plt.gca()
                ax.set_aspect('equal')
                fname = os.path.join(self.figure_path,
                                     f'roc-{self.total_mae}.png')
                plt.savefig(fname)
            plot_roc('ROC', true_cat, pred_cat)

            self.cur_step = 0
        self.cur_step += 1
        return super().on_epoch_end(epoch, logs)
