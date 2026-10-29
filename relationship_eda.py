import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter


# run data_clean.py first to create loss_cleaned.csv
data = pd.read_csv('loss_cleaned.csv', dtype={'County_FIPS': str})
data['State'] = data['StateName'].str.title()
data['County'] = data['CountyName'] + ', ' + data['State']

out_dir = 'relationships'
os.makedirs(out_dir, exist_ok=True)

# property = blue, crop = orange in every chart
PROPERTY = '#2a78d6'
CROP = '#eb6834'
plt.rcParams.update({
    'axes.edgecolor': '#c3c2b7', 'axes.labelcolor': '#52514e',
    'xtick.color': '#52514e', 'ytick.color': '#52514e',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.color': '#e1e0d9', 'grid.linewidth': 0.6,
    'axes.axisbelow': True,
})


def dollars(x, _=None):
    for size, suffix in [(1e9, 'B'), (1e6, 'M'), (1e3, 'k')]:
        if abs(x) >= size:
            return f'${x / size:.3g}{suffix}'
    return f'${x:g}'


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, name), dpi=120)
    plt.close(fig)
    print(f'saved {out_dir}/{name}')


# ---------------------------------------------------------------
# 1. correlation matrix
# ---------------------------------------------------------------
print('\n--- 1. correlation matrix ---')

numeric_cols = ['Year', 'CropDmg', 'CropDmg(ADJ 2024)', 'CropDmgPerCapita',
                'Crop_Damage_Duration', 'PropertyDmg', 'PropertyDmg(ADJ 2024)',
                'PropertyDmgPerCapita', 'Property_Damage_Duration', 'Duration_Days',
                'Records']

# spearman compares ranks, so the huge outliers don't distort it the way
# they would distort a regular (pearson) correlation on raw dollars
corr = data[numeric_cols].corr(method='spearman')

# diverging: red = negative, gray = none, blue = positive
cmap = LinearSegmentedColormap.from_list('div', ['#c23b3a', '#f0efec', '#1c5cab'])
fig, ax = plt.subplots(figsize=(10, 8.5))
im = ax.imshow(corr, cmap=cmap, vmin=-1, vmax=1)
ax.grid(False)
ax.set_xticks(range(len(numeric_cols)), numeric_cols, rotation=45, ha='right')
ax.set_yticks(range(len(numeric_cols)), numeric_cols)
for i in range(len(numeric_cols)):
    for j in range(len(numeric_cols)):
        value = corr.iloc[i, j]
        ax.text(j, i, f'{value:.2f}', ha='center', va='center', fontsize=8,
                color='white' if abs(value) > 0.6 else '#0b0b0b')
fig.colorbar(im, ax=ax, shrink=0.8, label='Spearman correlation')
ax.set_title('Correlation between numeric columns (Spearman)')
save(fig, 'correlation_matrix.png')

pairs = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack()
print('strongest pairs:')
print(pairs.sort_values(ascending=False).head(8).round(2).to_string())


# ---------------------------------------------------------------
# 2. trends over time
# ---------------------------------------------------------------
print('\n--- 2. trends over time ---')

by_year = data.groupby('Year').agg(
    property_total=('PropertyDmg(ADJ 2024)', 'sum'),
    crop_total=('CropDmg(ADJ 2024)', 'sum'),
    property_median=('PropertyDmg(ADJ 2024)', 'median'),
    counties=('County_FIPS', 'nunique'),
    records=('Records', 'sum'),
)

panels = [
    ('property_total', 'Total property damage (2024 $)', PROPERTY, True),
    ('crop_total', 'Total crop damage (2024 $)', CROP, True),
    ('property_median', 'Median property damage per flooded county (2024 $)', PROPERTY, True),
    ('counties', 'Counties with a recorded flood', '#52514e', False),
    ('records', 'Flood records', '#52514e', False),
]
fig, axes = plt.subplots(len(panels), 1, figsize=(12, 3 * len(panels)), sharex=True)
for ax, (col, title, color, money) in zip(axes, panels):
    ax.bar(by_year.index, by_year[col], color=color, width=0.8)
    ax.set_title(title, loc='left')
    if money:
        ax.yaxis.set_major_formatter(FuncFormatter(dollars))
axes[-1].set_xlabel('Year')
save(fig, 'trends_by_year.png')

# compare decades with medians so a single giant flood doesn't skew it
decade = (data['Year'] // 10) * 10
summary = data.groupby(decade).agg(
    county_years=('Records', 'size'),
    records_per_year=('Records', 'sum'),
    median_property=('PropertyDmg(ADJ 2024)', 'median'),
)
summary['records_per_year'] /= data.groupby(decade)['Year'].nunique()
print(summary.round(0).to_string())
print('top 5 years by total property damage:')
print(by_year['property_total'].nlargest(5).map(dollars).to_string())


# ---------------------------------------------------------------
# 3. geography: states
# ---------------------------------------------------------------
print('\n--- 3. states ---')

by_state = data.groupby('State').agg(
    property_total=('PropertyDmg(ADJ 2024)', 'sum'),
    crop_total=('CropDmg(ADJ 2024)', 'sum'),
    county_years=('Records', 'size'),
    counties=('County_FIPS', 'nunique'),
).sort_values('property_total')
by_state['property_share'] = by_state['property_total'] / by_state['property_total'].sum()

fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
for ax, col, title, color in [(axes[0], 'property_total', 'Total property damage, 1960-2024', PROPERTY),
                              (axes[1], 'crop_total', 'Total crop damage, 1960-2024', CROP)]:
    ax.barh(by_state.index, by_state[col], color=color, height=0.7)
    ax.set_title(title + ' (2024 $)', loc='left')
    ax.xaxis.set_major_formatter(FuncFormatter(dollars))
    ax.grid(axis='y', visible=False)
save(fig, 'state_totals.png')

# one histogram per state, same bins and x range so they can be compared
states = sorted(data['State'].unique())
bins = np.linspace(0, 10, 41)
n_cols = 4
n_rows = int(np.ceil(len(states) / n_cols))
fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 3.5 * n_rows), sharex=True)
for ax, state in zip(axes.flat, states):
    values = data.loc[data['State'] == state, 'log_PropertyDmgADJ']
    ax.hist(values, bins=bins, color=PROPERTY, edgecolor='white')
    ax.set_title(f'{state}\n(n={len(values)}, median={dollars(10 ** values.median() - 1)})')
    ax.set_xlabel('log10(PropertyDmg ADJ 2024 + 1)')
    ax.set_ylabel('Count')
for ax in axes.flat[len(states):]:
    ax.axis('off')
save(fig, 'state_distributions.png')

print(by_state.sort_values('property_total', ascending=False)
      .assign(property_total=lambda d: d['property_total'].map(dollars),
              crop_total=lambda d: d['crop_total'].map(dollars),
              property_share=lambda d: (d['property_share'] * 100).round(1))
      .to_string())


# ---------------------------------------------------------------
# 4. geography: counties that dominate losses
# ---------------------------------------------------------------
print('\n--- 4. counties ---')

data['total_adj'] = data['PropertyDmg(ADJ 2024)'] + data['CropDmg(ADJ 2024)']
by_county = data.groupby('County').agg(
    State=('State', 'first'),
    property_total=('PropertyDmg(ADJ 2024)', 'sum'),
    crop_total=('CropDmg(ADJ 2024)', 'sum'),
    total=('total_adj', 'sum'),
    flood_years=('Year', 'nunique'),
).sort_values('total', ascending=False)

# how concentrated are the losses?
share = by_county['total'].cumsum() / by_county['total'].sum()
n_counties = len(by_county)
for pct in [0.01, 0.05, 0.10]:
    k = max(1, int(round(n_counties * pct)))
    print(f'top {pct:.0%} of counties ({k}) hold {share.iloc[k - 1]:.0%} of all damage')

# top 15 overall, property and crop stacked with a white gap between them
top = by_county.head(15).iloc[::-1]
fig, ax = plt.subplots(figsize=(11, 7))
ax.barh(top.index, top['property_total'], color=PROPERTY, height=0.7,
        label='Property', edgecolor='white', linewidth=1)
ax.barh(top.index, top['crop_total'], left=top['property_total'], color=CROP,
        height=0.7, label='Crop', edgecolor='white', linewidth=1)
ax.xaxis.set_major_formatter(FuncFormatter(dollars))
ax.grid(axis='y', visible=False)
ax.set_title('Top 15 counties by total flood damage, 1960-2024 (2024 $)', loc='left')
ax.legend(loc='lower right', frameon=False)
save(fig, 'top_counties.png')

# top 5 counties within each state
fig, axes = plt.subplots(n_rows, n_cols, figsize=(5.5 * n_cols, 3.2 * n_rows))
for ax, state in zip(axes.flat, states):
    state_top = by_county[by_county['State'] == state].head(5).iloc[::-1]
    labels = state_top.index.str.replace(f', {state}', '', regex=False)
    ax.barh(labels, state_top['total'], color=PROPERTY, height=0.65)
    state_share = state_top['total'].sum() / by_county.loc[by_county['State'] == state, 'total'].sum()
    ax.set_title(f'{state}\n(top 5 = {state_share:.0%} of state damage)')
    ax.xaxis.set_major_formatter(FuncFormatter(dollars))
    ax.grid(axis='y', visible=False)
for ax in axes.flat[len(states):]:
    ax.axis('off')
save(fig, 'top_counties_by_state.png')

print(by_county.head(10).assign(
    property_total=lambda d: d['property_total'].map(dollars),
    crop_total=lambda d: d['crop_total'].map(dollars),
    total=lambda d: d['total'].map(dollars)).to_string())


# ---------------------------------------------------------------
# 5. crop vs property damage
# ---------------------------------------------------------------
print('\n--- 5. crop vs property ---')

has_property = data['PropertyDmg'] > 0
has_crop = data['CropDmg'] > 0
groups = pd.Series({
    'Property only': (has_property & ~has_crop).sum(),
    'Both': (has_property & has_crop).sum(),
    'Crop only': (~has_property & has_crop).sum(),
    'Neither': (~has_property & ~has_crop).sum(),
})
print((groups / len(data) * 100).round(1).astype(str).add('%').to_string())

# among county-years with property damage, how often is there crop damage too?
print(f'P(crop damage | property damage) = {has_crop[has_property].mean():.0%}')

both = data[has_property & has_crop]
rho = both['log_PropertyDmgADJ'].corr(both['log_CropDmgADJ'], method='spearman')
print(f'when both occur, spearman correlation of the amounts = {rho:.2f}')

fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), gridspec_kw={'width_ratios': [1, 1.4]})
axes[0].bar(groups.index, groups.values, color='#52514e', width=0.6)
for i, count in enumerate(groups.values):
    axes[0].text(i, count, f'{count / len(data):.0%}', ha='center', va='bottom', color='#0b0b0b')
axes[0].set_title('Which damage types occur together?', loc='left')
axes[0].set_ylabel('County-years')
axes[0].grid(axis='x', visible=False)

axes[1].scatter(both['log_PropertyDmgADJ'], both['log_CropDmgADJ'], s=8, alpha=0.25,
                color=PROPERTY, edgecolors='none')
axes[1].set_title(f'Amounts when both occur (n={len(both)}, Spearman={rho:.2f})', loc='left')
axes[1].set_xlabel('log10(PropertyDmg ADJ 2024 + 1)')
axes[1].set_ylabel('log10(CropDmg ADJ 2024 + 1)')
save(fig, 'crop_vs_property.png')
