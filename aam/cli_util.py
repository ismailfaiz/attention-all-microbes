import click


def aam_model_options(func):
    model_options = [
        click.option('--batch-size',
                     default=8,
                     type=int),
        click.option('--train-percent',
                     default=0.8,
                     type=float),
        click.option('--epochs',
                     default=100,
                     type=int),
        click.option('--repeat',
                     default=1,
                     type=int),
        click.option('--dropout',
                     default=0.5,
                     type=float),
        click.option('--pca-hidden-dim',
                     default=64,
                     type=int),
        click.option('--pca-heads',
                     default=4,
                     type=int),
        click.option('--dff',
                     default=2048,
                     type=int),
        click.option('--d-model',
                     default=64,
                     type=int),
        click.option('--enc_layers',
                     default=6,
                     type=int),
        click.option('--enc-heads',
                     default=4,
                     type=int),
        click.option('--output-dim',
                     default=1,
                     type=int),
        click.option('--lr',
                     default=0.001,
                     type=float)
    ]

    for option in reversed(model_options):
        func = option(func)
    return func
