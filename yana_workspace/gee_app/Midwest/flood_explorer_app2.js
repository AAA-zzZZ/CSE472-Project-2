// Midwest Flood Impact Explorer (CSE 472, Project 2)
//
// Explore the model's input data (PRISM, ERA5-Land, GHSL, NLCD, terrain) and its predictions for the
// 12 Midwest states. Paste into the Earth Engine Code Editor (https://code.earthengine.google.com)
// and press Run.
//
// Setup: upload yana_workspace/gee_app/Midwest/midwest_flood_app_table.csv as a table asset, then make
// sure ASSET_ID below matches where you saved it. The table comes from build_midwest_app_table.py.
//
// Adapted from missouri_tester/flood_explorer_app.js: a state selector (Missouri by default, or all 12
// states together), the 12-state LightGBM predictions, rank within the state and across the Midwest,
// and colour ranges set from the Midwest table (1st to 99th percentile).
//
// Loss is predicted as a class (order of magnitude), not in dollars (loss_class_model.py):
// minor under $10k, moderate $10k-$100k, major $100k-$1M, severe $1M or more. Counties are ranked by
// the chance of a severe loss, P(damage) x P($1M or more | damage).

var ASSET_ID = 'projects/flood-513221/assets/midwest_flood_app_table';

// ---------- Study area and prediction table ----------
// n = counties in the table; top = the state's top 5% of counties (the 'top5' column)
var STATES = {
  IA: {fips: '19', name: 'Iowa', n: 99, top: 5},
  IL: {fips: '17', name: 'Illinois', n: 102, top: 5},
  IN: {fips: '18', name: 'Indiana', n: 92, top: 5},
  KS: {fips: '20', name: 'Kansas', n: 105, top: 5},
  MI: {fips: '26', name: 'Michigan', n: 83, top: 4},
  MN: {fips: '27', name: 'Minnesota', n: 87, top: 4},
  MO: {fips: '29', name: 'Missouri', n: 115, top: 6},
  NE: {fips: '31', name: 'Nebraska', n: 93, top: 5},
  ND: {fips: '38', name: 'North Dakota', n: 53, top: 3},
  OH: {fips: '39', name: 'Ohio', n: 88, top: 4},
  SD: {fips: '46', name: 'South Dakota', n: 66, top: 3},
  WI: {fips: '55', name: 'Wisconsin', n: 72, top: 4}
};
var ALL = 'ALL';
var N_MIDWEST = 1055;
var DEFAULT_STATE = 'MO';
var STATE_BY_FIPS = {};
Object.keys(STATES).forEach(function (abbr) { STATE_BY_FIPS[STATES[abbr].fips] = abbr; });

var allCounties = ee.FeatureCollection('TIGER/2018/Counties')
  .filter(ee.Filter.inList('STATEFP', Object.keys(STATE_BY_FIPS)))
  .map(function (f) { return f.set('key', ee.String('G').cat(f.get('GEOID'))); });
var table = ee.FeatureCollection(ASSET_ID);

// the current view: one state or all 12 (set by setState)
var stateAbbr = DEFAULT_STATE;
var counties = allCounties;
var stateRows = table;

function setState(abbr) {
  stateAbbr = abbr;
  if (abbr === ALL) {
    counties = allCounties;
    stateRows = table;
  } else {
    counties = allCounties.filter(ee.Filter.eq('STATEFP', STATES[abbr].fips));
    stateRows = table.filter(ee.Filter.eq('state', abbr));
  }
}
function areaName() { return stateAbbr === ALL ? 'the Midwest' : STATES[stateAbbr].name; }
setState(DEFAULT_STATE);

// ---------- Palettes ----------
var HEAT = ['#ffffcc', '#fed976', '#fd8d3c', '#e31a1c', '#800026'];
var BLUE = ['#f7fbff', '#c6dbef', '#6baed6', '#2171b5', '#08306b'];
var GREEN = ['#f7fcf5', '#c7e9c0', '#74c476', '#238b45', '#00441b'];
var PURPLE = ['#fcfbfd', '#dadaeb', '#9e9ac8', '#6a51a3', '#3f007d'];
var GRAY = ['#ffffff', '#bdbdbd', '#737373', '#252525'];
var EARTH = ['#1a9850', '#a6d96a', '#ffffbf', '#fdae61', '#a50026'];
var NLCD_VALUES = [11, 12, 21, 22, 23, 24, 31, 41, 42, 43, 52, 71, 81, 82, 90, 95];
var NLCD_COLORS = ['#466b9f', '#d1def8', '#dec5c5', '#d99282', '#eb0000', '#ab0000', '#b3ac9f',
  '#68ab5f', '#1c5f2c', '#b5c58f', '#ccb879', '#dfdfc2', '#dcd939', '#ab6c28', '#b8d9eb', '#6c9fb8'];
var NLCD_NAMES = ['Open water', 'Perennial ice/snow', 'Developed, open space', 'Developed, low',
  'Developed, medium', 'Developed, high', 'Barren', 'Deciduous forest', 'Evergreen forest',
  'Mixed forest', 'Shrub/scrub', 'Grassland', 'Pasture/hay', 'Cultivated crops', 'Woody wetlands',
  'Emergent wetlands'];
var NLCD_CLASSES = {names: NLCD_NAMES, colors: NLCD_COLORS};
// loss classes 1-4 (0 = no damage); the same edges as loss_class_model.py
var LOSS_NAMES = ['No damage', 'Minor (under $10k)', 'Moderate ($10k to $100k)', 'Major ($100k to $1M)',
  'Severe ($1M or more)'];
var LOSS_KEYS = ['none', 'minor', 'moderate', 'major', 'severe'];
var LOSS_COLORS = ['#fed976', '#fd8d3c', '#e31a1c', '#800026'];
var LOSS_CLASSES = {names: LOSS_NAMES.slice(1), colors: LOSS_COLORS};

// ---------- Number formats ----------
function usd(v) {
  if (v === null || v === undefined) { return 'n/a'; }
  if (v >= 1e6) { return '$' + (v / 1e6).toFixed(1) + 'M'; }
  if (v >= 1e3) { return '$' + (v / 1e3).toFixed(0) + 'k'; }
  return '$' + v.toFixed(0);
}
function plain(v) { return String(Math.round(v * 1000) / 1000); }
function pct(v) { return (v * 100).toFixed(0) + '%'; }
// one decimal below 10%, where most chances of a large loss sit
function pct1(v) { return v < 0.1 ? (v * 100).toFixed(1) + '%' : pct(v); }
function per100(v) { return (v * 100).toFixed(1); }

// ---------- Source datasets (the same IDs and bands as the export scripts) ----------
function monthStart(y, m) { return ee.Date.fromYMD(y, m, 1); }
function prismMonth(y, m) {
  var s = monthStart(y, m);
  return ee.ImageCollection('OREGONSTATE/PRISM/ANd').filterDate(s, s.advance(1, 'month'));
}
function era5Day1(y, m) {
  var s = monthStart(y, m);
  return ee.Image(ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
    .filterDate(s, s.advance(2, 'day')).first());
}
function era5MonthlyMelt(y, m) {
  var s = monthStart(y, m);
  return ee.Image(ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
    .filterDate(s, s.advance(1, 'month')).first()).select('snowmelt_sum').multiply(1000);
}
function nlcdYear(id, y) {
  return ee.Image(ee.ImageCollection(id)
    .filter(ee.Filter.calendarRange(y, y, 'year')).first()).select([0]);
}
function landCover(y) {
  return nlcdYear('projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER', y);
}
// GHSL images are 5 years apart: interpolate linearly between the two around the year
function ghsl(y) {
  var lo = Math.max(1995, Math.min(2020, Math.floor(y / 5) * 5)), w = (y - lo) / 5;
  var img = function (e) { return ee.Image('JRC/GHSL/P2023A/GHS_BUILT_S/' + e).select('built_surface'); };
  return img(lo).multiply(1 - w).add(img(lo + 5).multiply(w));
}
// wettest 5 days: trailing 5-day windows that end on a day of the month, as in w_indices.py's rx5
function rx5(y, m) {
  var s = monthStart(y, m);
  var n = s.advance(1, 'month').difference(s, 'day');
  var sums = ee.List.sequence(0, n.subtract(1)).map(function (i) {
    var end = s.advance(ee.Number(i).add(1), 'day');
    return ee.ImageCollection('OREGONSTATE/PRISM/ANd').filterDate(end.advance(-5, 'day'), end).select('ppt').sum();
  });
  return ee.ImageCollection.fromImages(sums).max();
}
function dem() {
  var col = ee.ImageCollection('USGS/3DEP/10m_collection').filterBounds(counties);
  return col.mosaic().setDefaultProjection(ee.Image(col.first()).projection()).rename('elev');
}
function hand() { return ee.Image('MERIT/Hydro/v1_0_1').select('hnd'); }

// ---------- Layer catalogue ----------
// county layers colour each county by a column of the table; raster layers show the source data.
// Colour ranges are the 1st to 99th percentile of the Midwest table (build_midwest_app_table.py).
// classes: {names, colors} for a categorical layer whose values run min, min + 1, ..., max
function county(prop, min, max, palette, fmt, unit, note, maskZero, classes) {
  return {type: 'county', prop: prop, min: min, max: max, palette: palette, fmt: fmt, unit: unit,
          note: note, maskZero: !!maskZero, classes: classes};
}
function raster(image, min, max, palette, unit, note, scale, maskZero, classes) {
  return {type: 'raster', image: image, min: min, max: max, palette: palette, fmt: plain, unit: unit,
          note: note, scale: scale, maskZero: !!maskZero, classes: classes};
}

var GROUPS = {
  'Model predictions': {
    'Chance of any damage': county('p_damage', 0, 0.6, HEAT, pct, 'probability',
      'LightGBM part 1: the chance the county records any flood damage that month.'),
    'Likely loss class if damage occurs': county('likely_class', 1, 4, LOSS_COLORS, plain, 'class',
      'LightGBM part 2: the most likely of the four loss classes, if the county has any damage. ' +
      'Read it with the chance of any damage: most counties have little chance of damage in most months.',
      false, LOSS_CLASSES),
    // max is the number of counties in the selected state (largest state when all are shown)
    'Rank within the state': county('rank', 1, 'stateCount', HEAT.slice().reverse(), plain, '1 = highest risk',
      'Counties ordered by the chance of a severe loss within their own state in the selected month.'),
    'Rank across the Midwest': county('rank_midwest', 1, N_MIDWEST, HEAT.slice().reverse(), plain,
      '1 = highest risk of 1,055', 'All 1,055 counties of the 12 states ordered by the chance of a severe loss in the selected month.'),
    'Recorded loss class (SHELDUS)': county('actual_class', 1, 4, LOSS_COLORS, plain, 'class',
      'What was recorded, as a loss class. Blank counties have no SHELDUS record that month.', true, LOSS_CLASSES)
  },
  'Model inputs (county values)': {
    'Monthly rain': county('p_month', 0, 300, BLUE, plain, 'mm', 'p_month, from PRISM. Same month as the prediction.'),
    'Wettest 5 days / 10-year level': county('rx5_rl_ratio', 0, 1.3, BLUE, plain, 'ratio; 1 = a 10-year event',
      'rx5_rl_ratio, from PRISM, with a 2000-2009 baseline.'),
    'Snowmelt': county('snowmelt_mm', 0, 65, BLUE, plain, 'mm', 'snowmelt_mm, from ERA5-Land. Same month.'),
    'Frost days': county('frost_days', 0, 31, PURPLE, plain, 'days with Tmin below 0 C', 'frost_days, from PRISM.'),
    'Soil wetness percentile': county('sm_root_pct', 0, 1, GREEN, pct, 'vs 1950-1999',
      'sm_root_pct, from ERA5-Land, on day 1 of the month.'),
    'Snowpack': county('swe_mm', 0, 80, BLUE, plain, 'mm of water', 'swe_mm, from ERA5-Land, on day 1 of the month.'),
    '10-year 5-day rain': county('c_rx5_rl10_mm', 65, 210, BLUE, plain, 'mm', 'c_rx5_rl10_mm, from PRISM 2000-2009. Fixed for each county.'),
    'Built-up surface (log)': county('log_built_surface', 13.4, 18.7, HEAT, plain, 'ln of m2, year - 1',
      'log_built_surface, from GHSL, interpolated between 5-year images.'),
    'Paved share': county('impervious_mean', 0, 25, GRAY, plain, '%, year - 1', 'impervious_mean, from Annual NLCD.'),
    'Land under 5 m above drainage': county('hand_lt5_share', 0.1, 1, BLUE, pct, 'share of county', 'hand_lt5_share, from MERIT Hydro. Fixed for each county.'),
    'County land area (log)': county('log_land_km2', 6.2, 8.8, GRAY, plain, 'ln of km2', 'log_land_km2, from Census TIGER. Fixed for each county.'),
    'Wetland share': county('wetland_share', 0, 0.3, GREEN, pct, 'share of county, year - 1', 'wetland_share, from Annual NLCD.')
  },
  // not inputs of the forecast model: the adaptation (A) variables of adjustment_models.py,
  // all from year - 1 as in merge_panel.py
  'Adaptation (county values)': {
    'Flood insurance': county('nfip_policies_per_hu', 0, 0.05, GREEN, per100, 'NFIP policies per 100 homes, year - 1',
      'nfip_policies_per_hu, from FEMA NFIP Redacted Policies v3 (in force on 1 July) and census housing units. ' +
      'The clearest adaptation result: the same storm does less damage where more homes are insured.'),
    'Community Rating System class': county('crs_best_class', 5, 10, GREEN.slice().reverse(), plain,
      'best class in the county, year - 1 (10 = not in CRS)',
      'crs_best_class, from crsClassCode on the NFIP policies. Lower is better floodplain management; ' +
      'darker = better. Only about 200 of the 1,055 counties ever take part.'),
    'Median household income': county('median_income', 40000, 110000, GREEN, usd, '2024 dollars, year - 1',
      'median_income, from the census and ACS (census_features.py). Money to protect property and recover.'),
    'Homes built before 1980': county('built_pre1980_share', 0.28, 0.87, PURPLE, pct, 'share of homes, year - 1',
      'built_pre1980_share, from the census and ACS. Older building standards: higher = less prepared.'),
    'Wetland share': county('wetland_share', 0, 0.3, GREEN, pct, 'share of county, year - 1',
      'wetland_share, from Annual NLCD. Natural water storage (also a model input).')
  },
  'PRISM': {
    'Monthly rain': raster(function (y, m) { return prismMonth(y, m).select('ppt').sum(); },
      0, 300, BLUE, 'mm', 'OREGONSTATE/PRISM/ANd, sum of daily ppt.', 4000),
    'Wettest single day': raster(function (y, m) { return prismMonth(y, m).select('ppt').max(); },
      0, 100, BLUE, 'mm', 'OREGONSTATE/PRISM/ANd, maximum daily ppt.', 4000),
    'Wettest 5 days': raster(rx5, 0, 150, BLUE, 'mm',
      'OREGONSTATE/PRISM/ANd, largest 5-day total (rx5). The model divides it by the 10-year level.', 4000),
    'Frost days': raster(function (y, m) {
      return prismMonth(y, m).select('tmin').map(function (d) { return d.lt(0).toInt(); }).sum();
    }, 0, 31, PURPLE, 'days', 'OREGONSTATE/PRISM/ANd, days with tmin below 0 C.', 4000)
  },
  'ERA5-Land': {
    'Root-zone soil water': raster(function (y, m) {
      var d = era5Day1(y, m);
      return d.select('volumetric_soil_water_layer_1').multiply(7)
        .add(d.select('volumetric_soil_water_layer_2').multiply(21))
        .add(d.select('volumetric_soil_water_layer_3').multiply(72)).divide(100);
    }, 0.15, 0.45, GREEN, 'm3/m3', 'Day 1 of the month, 0-100 cm. The model converts this to a percentile.', 11000),
    'Snowpack': raster(function (y, m) {
      return era5Day1(y, m).select('snow_depth_water_equivalent').multiply(1000);
    }, 0, 100, BLUE, 'mm of water', 'Day 1 of the month.', 11000, true),
    'Snowmelt': raster(era5MonthlyMelt, 0, 70, BLUE, 'mm', 'Monthly total.', 11000, true)
  },
  'GHSL': {
    'Built-up surface': raster(function (y) { return ghsl(y - 1); }, 0, 3000, HEAT, 'm2 per 100 m cell',
      'JRC/GHSL/P2023A/GHS_BUILT_S, year - 1, interpolated between 5-year images as in the model.', 100, true)
  },
  'NLCD': {
    'Land cover': raster(function (y) { return landCover(y - 1).remap(NLCD_VALUES, ee.List.sequence(0, 15)); },
      0, 15, NLCD_COLORS, 'class', 'Annual NLCD, year - 1.', 30, false, NLCD_CLASSES),
    'Impervious surface': raster(function (y) {
      return nlcdYear('projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/FRACTIONAL_IMPERVIOUS_SURFACE', y - 1);
    }, 0, 80, HEAT, '%', 'Annual NLCD, year - 1.', 30, true),
    'Wetlands': raster(function (y) {
      var lc = landCover(y - 1);
      return lc.eq(90).or(lc.eq(95)).selfMask();
    }, 0, 1, ['#2171b5', '#2171b5'], 'present', 'Annual NLCD classes 90 and 95, year - 1.', 30)
  },
  'Terrain': {
    // the Midwest rises from about 100 m (Ohio and Mississippi valleys) to over 1,000 m (western Dakotas, Nebraska, Kansas)
    'Elevation': raster(function () { return dem(); }, 100, 1000, EARTH, 'm', 'USGS 3DEP 10 m.', 90),
    'Slope': raster(function () { return ee.Terrain.slope(dem()); }, 0, 15, EARTH, 'degrees', 'From USGS 3DEP.', 90),
    'Height above drainage': raster(function () { return hand(); }, 0, 30, BLUE.slice().reverse(), 'm',
      'MERIT Hydro hnd. Low values sit close to streams.', 90),
    'Land under 5 m above drainage': raster(function () { return hand().lt(5).selfMask(); }, 0, 1,
      ['#08519c', '#08519c'], 'present', 'MERIT Hydro. The county share of this area is a model input.', 90)
  }
};

// ---------- Controls ----------
var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December'];
var FIRST_PRED_YEAR = 2017; // the prediction table covers 2017-2023; source maps go back to 2000
var YEARS = [];
for (var yr = 2000; yr <= 2023; yr++) { YEARS.push(yr); }
var selected = null;   // the clicked county: {geoid, name, state}
var requestId = 0;     // ignores slow replies after the selection has changed

var stateItems = Object.keys(STATES)
  .sort(function (a, b) { return STATES[a].name < STATES[b].name ? -1 : 1; })
  .map(function (abbr) { return {label: STATES[abbr].name, value: abbr}; });
stateItems.unshift({label: 'All 12 Midwest states', value: ALL});
var stateSelect = ui.Select({items: stateItems, value: DEFAULT_STATE, onChange: function (abbr) {
  setState(abbr);
  clearSelection();
  titleLabel.setValue(abbr === ALL ? 'Midwest Flood Impact Explorer' : STATES[abbr].name + ' Flood Impact Explorer');
  zoomToState();
  redraw();
}, style: {stretch: 'horizontal'}});

var groupSelect = ui.Select({items: Object.keys(GROUPS), value: 'Model predictions',
  onChange: function (group) {
    var names = Object.keys(GROUPS[group]);
    layerSelect.items().reset(names);
    // two groups can start with the same layer name, so redraw explicitly
    layerSelect.setValue(names[0], false);
    redraw();
  }, style: {stretch: 'horizontal'}});
var layerSelect = ui.Select({items: Object.keys(GROUPS['Model predictions']), value: 'Chance of any damage',
  onChange: redraw, style: {stretch: 'horizontal'}});
var yearSelect = ui.Select({items: YEARS.map(function (y) { return {label: String(y), value: y}; }),
  value: 2017, onChange: redraw});
var monthSelect = ui.Select({items: MONTHS.map(function (name, i) { return {label: name, value: i + 1}; }),
  value: 4, onChange: redraw});
var topBox = ui.Checkbox({label: '', value: true, onChange: redraw});

function step(delta) {
  var total = yearSelect.getValue() * 12 + monthSelect.getValue() - 1 + delta;
  var y = Math.floor(total / 12), m = total % 12 + 1;
  if (y < YEARS[0] || y > YEARS[YEARS.length - 1]) { return; }
  yearSelect.setValue(y, false);
  monthSelect.setValue(m, false);
  redraw();
}

var HEADER = {fontWeight: 'bold', fontSize: '14px', margin: '12px 8px 2px 8px'};
var SMALL = {fontSize: '11px', color: '#555555', margin: '2px 8px'};
var titleLabel = ui.Label(STATES[DEFAULT_STATE].name + ' Flood Impact Explorer',
  {fontWeight: 'bold', fontSize: '18px', margin: '8px'});
var noteLabel = ui.Label('', SMALL);
var legend = ui.Panel();
var detail = ui.Panel();
var chartPanel = ui.Panel();
var statusLabel = ui.Label('Click a county on the map.', {margin: '4px 8px'});

var panel = ui.Panel({
  widgets: [
    titleLabel,
    ui.Label('Predicted monthly flood property loss class for the 12 Midwest states, used to rank ' +
      'counties for emergency resources, with the data behind the model.', {margin: '2px 8px'}),
    ui.Label('State', HEADER), stateSelect,
    ui.Label('Layer', HEADER), groupSelect, layerSelect,
    ui.Label('The PRISM, ERA5-Land, GHSL, NLCD and Terrain maps are for reference and are not the ' +
      'actual model inputs. The model uses the county values in the "Model inputs" group. The ' +
      '"Adaptation" group is not a model input: it maps how prepared each county is, for the ' +
      'climate and adaptation analysis.', SMALL),
    ui.Label('Month', HEADER),
    ui.Panel([yearSelect, monthSelect], ui.Panel.Layout.flow('horizontal')),
    ui.Panel([ui.Button({label: 'Previous', onClick: function () { step(-1); }}),
              ui.Button({label: 'Next', onClick: function () { step(1); }})],
             ui.Panel.Layout.flow('horizontal')),
    topBox, legend, noteLabel,
    ui.Label('County', HEADER), statusLabel, detail, chartPanel,
    ui.Label('About the predictions', HEADER),
    ui.Label('One LightGBM hurdle model fitted on all 1,055 counties of the 12 states for 2000-2016 ' +
      '(the state is one of its inputs) and shown for 2017-2023. Part 1 gives the chance of any ' +
      'damage; part 2 gives the chance of each loss class if damage occurs. Predictions were ' +
      'computed outside Earth Engine and uploaded as a table.', SMALL),
    ui.Label('Loss classes are orders of magnitude: minor under $10k, moderate $10k to $100k, major ' +
      '$100k to $1M, severe $1M or more (2024 dollars). The model does not predict dollar amounts: ' +
      'in 2017-2023 its most likely class was right for 41% of damage months and within one class ' +
      'for 86%.', SMALL),
    ui.Label('Predictions use the rain observed that month, so they are not true forecasts.', SMALL)
  ],
  style: {width: '380px', padding: '4px'}
});
ui.root.insert(0, panel);
Map.setOptions('ROADMAP');
Map.style().set('cursor', 'crosshair');

var highlight = ui.Map.Layer(ee.Image(), {}, 'Selected county', false);

function zoomToState() { Map.centerObject(counties, stateAbbr === ALL ? 5 : 7); }

function clearSelection() {
  selected = null;
  requestId++;
  highlight.setShown(false);
  detail.clear();
  chartPanel.clear();
  statusLabel.setValue('Click a county on the map.');
}

// ---------- Drawing ----------
// the largest state's count when all states are shown, so every state's rank fits the colour scale
function stateCount() {
  if (stateAbbr !== ALL) { return STATES[stateAbbr].n; }
  return Math.max.apply(null, Object.keys(STATES).map(function (a) { return STATES[a].n; }));
}
function currentLayer() {
  var layer = GROUPS[groupSelect.getValue()][layerSelect.getValue()];
  if (layer.max !== 'stateCount') { return layer; }
  var copy = {};
  Object.keys(layer).forEach(function (k) { copy[k] = layer[k]; });
  copy.max = stateCount();
  return copy;
}
function ym() { return yearSelect.getValue() * 100 + monthSelect.getValue(); }

function joinedCounties() {
  var rows = stateRows.filter(ee.Filter.eq('ym', ym()));
  var joined = ee.Join.saveFirst('row').apply({
    primary: counties, secondary: rows,
    condition: ee.Filter.equals({leftField: 'key', rightField: 'key'})
  });
  return ee.FeatureCollection(joined).map(function (f) {
    return ee.Feature(f).copyProperties(ee.Feature(f.get('row')));
  });
}

function outline(fc, width) {
  return ee.Image().byte().paint({featureCollection: fc, color: 1, width: width});
}

function layerImage(layer, joined) {
  var image = layer.type === 'county'
    ? ee.Image().float().paint({featureCollection: joined, color: layer.prop})
    : ee.Image(layer.image(yearSelect.getValue(), monthSelect.getValue())).clipToCollection(counties);
  return layer.maskZero ? image.updateMask(image.gt(0)) : image;
}

function drawLegend(layer) {
  legend.clear();
  if (layer.classes) {
    layer.classes.names.forEach(function (name, i) {
      legend.add(ui.Panel([
        ui.Label('', {backgroundColor: layer.classes.colors[i], padding: '7px', margin: '2px 6px 2px 8px'}),
        ui.Label(name, {fontSize: '11px', margin: '2px 0'})
      ], ui.Panel.Layout.flow('horizontal')));
    });
    return;
  }
  legend.add(ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0),
    params: {bbox: [0, 0, 1, 0.1], dimensions: '300x12', format: 'png', min: 0, max: 1, palette: layer.palette},
    style: {stretch: 'horizontal', maxHeight: '18px', margin: '8px 8px 0 8px'}
  }));
  legend.add(ui.Panel([
    ui.Label(layer.fmt(layer.min), SMALL),
    ui.Label(layer.unit, {fontSize: '11px', color: '#555555', margin: '2px 8px', stretch: 'horizontal', textAlign: 'center'}),
    ui.Label(layer.fmt(layer.max), SMALL)
  ], ui.Panel.Layout.flow('horizontal')));
}

function redraw() {
  var layer = currentLayer();
  var joined = joinedCounties();
  topBox.setLabel(stateAbbr === ALL
    ? "Outline each state's top 5% of counties"
    : 'Outline the ' + STATES[stateAbbr].top + ' highest-risk counties');
  Map.layers().reset();
  Map.addLayer(layerImage(layer, joined), {min: layer.min, max: layer.max, palette: layer.palette},
    groupSelect.getValue() + ': ' + layerSelect.getValue());
  Map.addLayer(outline(counties, 1), {palette: ['#666666']}, 'County borders');
  if (stateAbbr === ALL) {
    Map.addLayer(ee.Image().byte().paint({featureCollection: ee.FeatureCollection('TIGER/2018/States')
      .filter(ee.Filter.inList('STATEFP', Object.keys(STATE_BY_FIPS))), color: 1, width: 2}),
      {palette: ['#222222']}, 'State borders');
  }
  if (topBox.getValue()) {
    Map.addLayer(outline(joined.filter(ee.Filter.eq('top5', 1)), 3), {palette: ['#00bcd4']}, 'Highest-risk counties');
  }
  Map.layers().add(highlight);
  var noPred = yearSelect.getValue() < FIRST_PRED_YEAR;
  noteLabel.setValue(layer.note + (layer.type === 'county' && noPred
    ? ' No county values before ' + FIRST_PRED_YEAR + ': pick a later year or a source-data layer.' : ''));
  drawLegend(layer);
  if (selected) { showCounty(); }
}

// ---------- County details ----------
function row(name, value) {
  return ui.Panel([
    ui.Label(name, {margin: '1px 8px', fontSize: '12px', stretch: 'horizontal'}),
    ui.Label(value, {margin: '1px 8px', fontSize: '12px', fontWeight: 'bold'})
  ], ui.Panel.Layout.flow('horizontal'));
}
function section(title) { return ui.Label(title, {fontWeight: 'bold', fontSize: '12px', margin: '8px 8px 2px 8px'}); }

function showCounty() {
  var mine = ++requestId;
  var key = 'G' + selected.geoid;
  var st = STATES[selected.state];
  var label = selected.name + ' County, ' + st.name;
  statusLabel.setValue(label + ': loading...');
  detail.clear();
  chartPanel.clear();
  var mineRows = table.filter(ee.Filter.eq('key', key));
  var query = ee.Feature(mineRows.filter(ee.Filter.eq('ym', ym())).first());
  query.toDictionary().evaluate(function (r, err) {
    if (mine !== requestId) { return; }
    if (err || !r) {
      if (yearSelect.getValue() < FIRST_PRED_YEAR) {
        statusLabel.setValue(label + ', ' + MONTHS[monthSelect.getValue() - 1] + ' ' +
          yearSelect.getValue() + ': no predictions before ' + FIRST_PRED_YEAR + '.');
        showRasterMean(mine);
      } else {
        statusLabel.setValue('No prediction found. Check that ASSET_ID points to the uploaded table.');
      }
      return;
    }
    statusLabel.setValue(label + ', ' + MONTHS[monthSelect.getValue() - 1] + ' ' + yearSelect.getValue());
    detail.add(section('Prediction'));
    detail.add(row('Chance of any damage', pct1(r.p_damage)));
    detail.add(row('Rank in ' + st.name, r.rank + ' of ' + st.n + (r.top5 ? ' (top 5%)' : '')));
    detail.add(row('Rank in the Midwest', r.rank_midwest + ' of ' + N_MIDWEST.toLocaleString()));
    // the predicted class is the one with the highest chance, shown first as a coloured banner
    var chances = [null];
    var best = 1;
    for (var k = 1; k <= 4; k++) {
      chances.push(r['p_' + LOSS_KEYS[k] + '_if_damage']);
      if (chances[k] > chances[best]) { best = k; }
    }
    detail.add(section('If damage occurs'));
    detail.add(ui.Label('Predicted loss class: ' + LOSS_NAMES[best] + ' (' + pct(chances[best]) + ' chance)', {
      fontWeight: 'bold', fontSize: '13px', padding: '6px', margin: '4px 8px',
      backgroundColor: LOSS_COLORS[best - 1], color: best >= 3 ? '#ffffff' : '#000000'
    }));
    detail.add(ui.Label('Chance of each class:', {fontSize: '11px', color: '#555555', margin: '4px 8px 0 8px'}));
    for (k = 1; k <= 4; k++) {
      detail.add(row((k === best ? '▶ ' : '    ') + LOSS_NAMES[k], pct(chances[k])));
    }
    detail.add(section('Recorded (SHELDUS)'));
    detail.add(row('Loss class', LOSS_NAMES[r.actual_class]));
    if (r.has_damage) { detail.add(row('Amount', usd(r.actual_loss))); }
    detail.add(section('Model inputs'));
    detail.add(row('Monthly rain', plain(r.p_month) + ' mm'));
    detail.add(row('Wettest 5 days / 10-year level', plain(r.rx5_rl_ratio)));
    detail.add(row('Snowmelt', plain(r.snowmelt_mm) + ' mm'));
    detail.add(row('Frost days', plain(r.frost_days)));
    detail.add(row('Soil wetness percentile', pct(r.sm_root_pct)));
    detail.add(row('Snowpack, day 1', plain(Math.max(r.swe_mm, 0)) + ' mm'));
    detail.add(row('10-year 5-day rain', plain(r.c_rx5_rl10_mm) + ' mm'));
    detail.add(row('Built-up surface, year - 1', (Math.exp(r.log_built_surface) / 1e6).toFixed(1) + ' km2'));
    detail.add(row('Paved share, year - 1', r.impervious_mean.toFixed(1) + '%'));
    detail.add(row('Land under 5 m above drainage', pct(r.hand_lt5_share)));
    detail.add(row('County land area', Math.exp(r.log_land_km2).toFixed(0) + ' km2'));
    detail.add(row('Wetland share, year - 1', (r.wetland_share * 100).toFixed(1) + '%'));
    if (r.nfip_policies_per_hu !== undefined) {
      detail.add(section('Adaptation (year - 1, not a model input)'));
      detail.add(row('Flood insurance policies per 100 homes', per100(r.nfip_policies_per_hu)));
      detail.add(row('Community Rating System class', r.crs_best_class >= 10 ? 'Not in CRS (10)' : plain(r.crs_best_class)));
      detail.add(row('Median household income', usd(r.median_income)));
      detail.add(row('Homes built before 1980', pct(r.built_pre1980_share)));
    }
    showRasterMean(mine);
  });

  // chances on the left axis; the recorded class on the right, whose window starts at 0.5 so
  // months without damage (class 0) are not drawn
  var chart = ui.Chart.feature.byFeature({features: mineRows.sort('ym'), xProperty: 'ym_label',
    yProperties: ['p_damage', 'actual_class']})
    .setChartType('LineChart')
    .setOptions({
      title: 'Chance of any damage (left) and recorded loss class (right: 1 minor to 4 severe)',
      legend: {position: 'bottom'},
      hAxis: {showTextEvery: 12, textStyle: {fontSize: 10}},
      vAxes: {0: {viewWindow: {min: 0, max: 1}, format: 'percent'},
              1: {viewWindow: {min: 0.5, max: 4.5}, ticks: [1, 2, 3, 4]}},
      series: {0: {labelInLegend: 'Chance of any damage', color: '#fd8d3c', lineWidth: 2, pointSize: 0, targetAxisIndex: 0},
               1: {labelInLegend: 'Recorded loss class', color: '#3f007d', lineWidth: 0, pointSize: 5, targetAxisIndex: 1}}
    });
  chartPanel.add(chart);
}

// the selected raster's average over the county, when a source layer is on the map
function showRasterMean(mine) {
  var layer = currentLayer();
  // land cover classes and yes/no masks have no meaningful average
  if (layer.type !== 'raster' || layer.classes || layer.unit === 'present') { return; }
  var name = layerSelect.getValue();
  var geometry = allCounties.filter(ee.Filter.eq('GEOID', selected.geoid)).geometry();
  var image = ee.Image(layer.image(yearSelect.getValue(), monthSelect.getValue())).rename('v');
  image.reduceRegion({reducer: ee.Reducer.mean(), geometry: geometry, scale: layer.scale,
                      bestEffort: true, maxPixels: 1e9}).get('v').evaluate(function (v, err) {
    if (mine !== requestId || err || v === null || v === undefined) { return; }
    detail.insert(0, row('County mean of ' + name, plain(v) + ' ' + layer.unit));
  });
}

Map.onClick(function (coords) {
  statusLabel.setValue('Finding the county...');
  counties.filterBounds(ee.Geometry.Point([coords.lon, coords.lat])).select(['GEOID', 'NAME', 'STATEFP'])
    .toList(1).evaluate(function (list, err) {
      if (err || !list || !list.length) {
        statusLabel.setValue('Click inside ' + areaName() + '.');
        return;
      }
      var p = list[0].properties;
      selected = {geoid: p.GEOID, name: p.NAME, state: STATE_BY_FIPS[p.STATEFP]};
      highlight.setEeObject(outline(allCounties.filter(ee.Filter.eq('GEOID', p.GEOID)), 4));
      highlight.setVisParams({palette: ['#000000']});
      highlight.setShown(true);
      showCounty();
    });
});

// a missing asset would otherwise fail silently
table.size().evaluate(function (n, err) {
  if (err) {
    statusLabel.setValue('Could not read the table. Upload the CSV and check ASSET_ID. ' + err);
  }
});

zoomToState();
redraw();
