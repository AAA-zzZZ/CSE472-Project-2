import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt



#plot cropdmg,cropdmgADJ2024, cropdmgpercapita, propertydmg, propertydmgADJ2024, propertydmgpercapita
#cropdmgduration, propertydmgduration, durationdays, records


data = pd.read_csv('loss_output_year_county.csv')

print(data.describe())


columns = ['CropDmg', 'CropDmg(ADJ 2024)', 'CropDmgPerCapita',
           'PropertyDmg', 'PropertyDmg(ADJ 2024)', 'PropertyDmgPerCapita',
           'Crop_Damage_Duration', 'Property_Damage_Duration', 'Duration_Days', 'Records']

out_dir = 'distributions'
os.makedirs(out_dir, exist_ok=True)

# values are heavily right-skewed with many zeros, so plot log10(x + 1)
image_paths = []
for col in columns:
    values = data[col]
    n_zero = (values == 0).sum()

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(np.log10(values + 1), bins=50, color='steelblue', edgecolor='white')
    ax.set_title(f'{col}\n(n={len(values)}, zeros={n_zero})')
    ax.set_xlabel(f'log10({col} + 1)')
    ax.set_ylabel('Count')
    fig.tight_layout()

    path = os.path.join(out_dir, col.replace(' ', '_').replace('(', '').replace(')', '') + '.png')
    fig.savefig(path, dpi=120)
    plt.close(fig)
    image_paths.append(path)

# compile the individual images into one big picture
n_cols = 4
n_rows = int(np.ceil(len(image_paths) / n_cols))
fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 4 * n_rows))
for ax, path in zip(axes.flat, image_paths):
    ax.imshow(plt.imread(path))
    ax.axis('off')
for ax in axes.flat[len(image_paths):]:
    ax.axis('off')
fig.tight_layout()
fig.savefig(os.path.join(out_dir, 'all_distributions.png'), dpi=120)
plt.close(fig)

# raw values with zeros dropped
raw_dir = os.path.join(out_dir, 'raw_nonzero')
os.makedirs(raw_dir, exist_ok=True)

raw_image_paths = []
for col in columns:
    values = data[col]
    nonzero = values[values != 0]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(nonzero, bins=50, color='darkorange', edgecolor='white')
    ax.set_title(f'{col} (zeros dropped)\n(n={len(nonzero)}, dropped={len(values) - len(nonzero)})')
    ax.set_xlabel(col)
    ax.set_ylabel('Count')
    fig.tight_layout()

    path = os.path.join(raw_dir, col.replace(' ', '_').replace('(', '').replace(')', '') + '.png')
    fig.savefig(path, dpi=120)
    plt.close(fig)
    raw_image_paths.append(path)

fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 4 * n_rows))
for ax, path in zip(axes.flat, raw_image_paths):
    ax.imshow(plt.imread(path))
    ax.axis('off')
for ax in axes.flat[len(raw_image_paths):]:
    ax.axis('off')
fig.tight_layout()
fig.savefig(os.path.join(out_dir, 'all_distributions_raw_nonzero.png'), dpi=120)
plt.close(fig)
