// Missouri Flood Impact Explorer (CSE 472, Project 2)
//
// Explore the model's input data (PRISM, ERA5-Land, GHSL, NLCD, terrain) and its predictions.
// Paste into the Earth Engine Code Editor (https://code.earthengine.google.com) and press Run.
//
// Setup: upload yana_workspace/gee_app/missouri_tester/mo_flood_app_table.csv as a table asset, then make sure
// ASSET_ID below matches where you saved it.

var ASSET_ID = 'projects/flood-513221/assets/mo_flood_app_table';

// ---------- Study area and prediction table ----------
var STATE_FIPS = '29';
var STATE_NAME = 'Missouri';
var N_COUNTIES = 115;
var TOP_N = 6; // top 5% of counties

var counties = ee.FeatureCollection('TIGER/2018/Counties')
  .filter(ee.Filter.eq('STATEFP', STATE_FIPS))
  .map(function (f) { return f.set('key', ee.String('G').cat(f.get('GEOID'))); });
var region = counties.geometry();
var table = ee.FeatureCollection(ASSET_ID);

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

// ---------- Number formats ----------
function usd(v) {
  if (v === null || v === undefined) { return 'n/a'; }
  if (v >= 1e6) { return '$' + (v / 1e6).toFixed(1) + 'M'; }
  if (v >= 1e3) { return '$' + (v / 1e3).toFixed(0) + 'k'; }
  return '$' + v.toFixed(0);
}
function usdLog(v) { return usd(Math.pow(10, v)); }
function plain(v) { return String(Math.round(v * 1000) / 1000); }
function pct(v) { return (v * 100).toFixed(0) + '%'; }

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
function ghsl(y) {
  var image = Math.max(1995, Math.min(2025, Math.round(y / 5) * 5));
  return ee.Image('JRC/GHSL/P2023A/GHS_BUILT_S/' + image).select('built_surface');
}
function dem() {
  var col = ee.ImageCollection('USGS/3DEP/10m_collection').filterBounds(region);
  return col.mosaic().setDefaultProjection(ee.Image(col.first()).projection()).rename('elev');
}
function hand() { return ee.Image('MERIT/Hydro/v1_0_1').select('hnd'); }

// ---------- Layer catalogue ----------
// county layers colour each county by a column of the table; raster layers show the source data.
function county(prop, min, max, palette, fmt, unit, note, maskZero) {
  return {type: 'county', prop: prop, min: min, max: max, palette: palette, fmt: fmt, unit: unit,
          note: note, maskZero: !!maskZero};
}
function raster(image, min, max, palette, unit, note, scale, maskZero, classes) {
  return {type: 'raster', image: image, min: min, max: max, palette: palette, fmt: plain, unit: unit,
          note: note, scale: scale, maskZero: !!maskZero, classes: classes};
}

var GROUPS = {
  'Model predictions': {
    'Expected loss': county('log10_expected_loss', 2, 7, HEAT, usdLog, '2024 dollars, log colour scale',
      'Chance of damage x expected size of the loss.'),
    'Chance of any damage': county('p_damage', 0, 0.6, HEAT, pct, 'probability',
      'LightGBM part 1: the chance the county records any flood damage that month.'),
    'Rank within the state': county('rank', 1, N_COUNTIES, HEAT.slice().reverse(), plain, '1 = highest expected loss',
      'Counties ordered by expected loss within the selected month.'),
    'Recorded loss (SHELDUS)': county('log10_actual_loss', 3, 8, PURPLE, usdLog, '2024 dollars, log colour scale',
      'What was recorded. Blank counties have no SHELDUS record that month.', true)
  },
  'Model inputs (county values)': {
    'Monthly rain': county('p_month', 0, 300, BLUE, plain, 'mm', 'p_month, from PRISM. Same month as the prediction.'),
    'Wettest 5 days / 10-year level': county('rx5_rl_ratio', 0, 1.3, BLUE, plain, 'ratio; 1 = a 10-year event',
      'rx5_rl_ratio, from PRISM, with a 2000-2009 baseline.'),
    'Snowmelt': county('snowmelt_mm', 0, 35, BLUE, plain, 'mm', 'snowmelt_mm, from ERA5-Land. Same month.'),
    'Frost days': county('frost_days', 0, 30, PURPLE, plain, 'days with Tmin below 0 C', 'frost_days, from PRISM.'),
    'Soil wetness percentile': county('sm_root_pct', 0, 1, GREEN, pct, 'vs 1950-1999',
      'sm_root_pct, from ERA5-Land, on day 1 of the month.'),
    'Snowpack': county('swe_mm', 0, 15, BLUE, plain, 'mm of water', 'swe_mm, from ERA5-Land, on day 1 of the month.'),
    '10-year 5-day rain': county('c_rx5_rl10_mm', 125, 210, BLUE, plain, 'mm', 'c_rx5_rl10_mm, from PRISM 2000-2009. Fixed for each county.'),
    'Built-up surface (log)': county('log_built_surface', 14.5, 18.6, HEAT, plain, 'ln of m2, year - 1',
      'log_built_surface, from GHSL, interpolated between 5-year images.'),
    'Paved share': county('impervious_mean', 0, 25, GRAY, plain, '%, year - 1', 'impervious_mean, from Annual NLCD.'),
    'Land under 5 m above drainage': county('hand_lt5_share', 0.1, 1, BLUE, pct, 'share of county', 'hand_lt5_share, from MERIT Hydro. Fixed for each county.'),
    'County land area (log)': county('log_land_km2', 6.5, 7.9, GRAY, plain, 'ln of km2', 'log_land_km2, from Census TIGER. Fixed for each county.'),
    'Wetland share': county('wetland_share', 0, 0.085, GREEN, pct, 'share of county, year - 1', 'wetland_share, from Annual NLCD.')
  },
  'PRISM': {
    'Monthly rain': raster(function (y, m) { return prismMonth(y, m).select('ppt').sum(); },
      0, 300, BLUE, 'mm', 'OREGONSTATE/PRISM/ANd, sum of daily ppt.', 4000),
    'Wettest single day': raster(function (y, m) { return prismMonth(y, m).select('ppt').max(); },
      0, 100, BLUE, 'mm', 'OREGONSTATE/PRISM/ANd, maximum daily ppt.', 4000),
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
    }, 0, 30, BLUE, 'mm of water', 'Day 1 of the month.', 11000, true),
    'Snowmelt': raster(era5MonthlyMelt, 0, 40, BLUE, 'mm', 'Monthly total.', 11000, true)
  },
  'GHSL': {
    'Built-up surface': raster(function (y) { return ghsl(y - 1); }, 0, 3000, HEAT, 'm2 per 100 m cell',
      'JRC/GHSL/P2023A/GHS_BUILT_S, 5-year image nearest year - 1. The model interpolates between images.', 100, true)
  },
  'NLCD': {
    'Land cover': raster(function (y) { return landCover(y - 1).remap(NLCD_VALUES, ee.List.sequence(0, 15)); },
      0, 15, NLCD_COLORS, 'class', 'Annual NLCD, year - 1.', 30, false, true),
    'Impervious surface': raster(function (y) {
      return nlcdYear('projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/FRACTIONAL_IMPERVIOUS_SURFACE', y - 1);
    }, 0, 80, HEAT, '%', 'Annual NLCD, year - 1.', 30, true),
    'Wetlands': raster(function (y) {
      var lc = landCover(y - 1);
      return lc.eq(90).or(lc.eq(95)).selfMask();
    }, 0, 1, ['#2171b5', '#2171b5'], 'present', 'Annual NLCD classes 90 and 95, year - 1.', 30)
  },
  'Terrain': {
    'Elevation': raster(function () { return dem(); }, 70, 500, EARTH, 'm', 'USGS 3DEP 10 m.', 90),
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
var YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023];
var selected = null;   // the clicked county: {geoid, name}
var requestId = 0;     // ignores slow replies after the selection has changed

var groupSelect = ui.Select({items: Object.keys(GROUPS), value: 'Model predictions',
  onChange: function (group) {
    var names = Object.keys(GROUPS[group]);
    layerSelect.items().reset(names);
    // two groups can start with the same layer name, so redraw explicitly
    layerSelect.setValue(names[0], false);
    redraw();
  }, style: {stretch: 'horizontal'}});
var layerSelect = ui.Select({items: Object.keys(GROUPS['Model predictions']), value: 'Expected loss',
  onChange: redraw, style: {stretch: 'horizontal'}});
var yearSelect = ui.Select({items: YEARS.map(function (y) { return {label: String(y), value: y}; }),
  value: 2017, onChange: redraw});
var monthSelect = ui.Select({items: MONTHS.map(function (name, i) { return {label: name, value: i + 1}; }),
  value: 4, onChange: redraw});
var topBox = ui.Checkbox({label: 'Outline the ' + TOP_N + ' highest-risk counties', value: true, onChange: redraw});

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
var noteLabel = ui.Label('', SMALL);
var legend = ui.Panel();
var detail = ui.Panel();
var chartPanel = ui.Panel();
var statusLabel = ui.Label('Click a county on the map.', {margin: '4px 8px'});

var panel = ui.Panel({
  widgets: [
    ui.Label(STATE_NAME + ' Flood Impact Explorer', {fontWeight: 'bold', fontSize: '18px', margin: '8px'}),
    ui.Label('Predicted monthly flood property loss, used to rank counties for emergency resources, ' +
      'with the data behind the model.', {margin: '2px 8px'}),
    ui.Label('Layer', HEADER), groupSelect, layerSelect,
    ui.Label('The PRISM, ERA5-Land, GHSL, NLCD and Terrain maps are for reference and are not the ' +
      'actual model inputs. The model uses the county values in the "Model inputs" group.', SMALL),
    ui.Label('Month', HEADER),
    ui.Panel([yearSelect, monthSelect], ui.Panel.Layout.flow('horizontal')),
    ui.Panel([ui.Button({label: 'Previous', onClick: function () { step(-1); }}),
              ui.Button({label: 'Next', onClick: function () { step(1); }})],
             ui.Panel.Layout.flow('horizontal')),
    topBox, legend, noteLabel,
    ui.Label('County', HEADER), statusLabel, detail, chartPanel,
    ui.Label('About the predictions', HEADER),
    ui.Label('LightGBM hurdle model fitted on Missouri counties for 2000-2016 and shown for ' +
      '2017-2023. Predictions were computed outside Earth Engine and uploaded as a table.', SMALL),
    ui.Label('Predictions use the rain observed that month, so they are not true forecasts. ' +
      'Dollar amounts are typically off by several times: use them to compare counties.', SMALL)
  ],
  style: {width: '380px', padding: '4px'}
});
ui.root.insert(0, panel);
Map.setOptions('ROADMAP');
Map.centerObject(counties, 7);
Map.style().set('cursor', 'crosshair');

var highlight = ui.Map.Layer(ee.Image(), {}, 'Selected county', false);

// ---------- Drawing ----------
function currentLayer() { return GROUPS[groupSelect.getValue()][layerSelect.getValue()]; }
function ym() { return yearSelect.getValue() * 100 + monthSelect.getValue(); }

function joinedCounties() {
  var rows = table.filter(ee.Filter.eq('ym', ym()));
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
    : ee.Image(layer.image(yearSelect.getValue(), monthSelect.getValue())).clip(region);
  return layer.maskZero ? image.updateMask(image.gt(0)) : image;
}

function drawLegend(layer) {
  legend.clear();
  if (layer.classes) {
    NLCD_NAMES.forEach(function (name, i) {
      legend.add(ui.Panel([
        ui.Label('', {backgroundColor: NLCD_COLORS[i], padding: '7px', margin: '2px 6px 2px 8px'}),
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
  Map.layers().reset();
  Map.addLayer(layerImage(layer, joined), {min: layer.min, max: layer.max, palette: layer.palette},
    groupSelect.getValue() + ': ' + layerSelect.getValue());
  Map.addLayer(outline(counties, 1), {palette: ['#666666']}, 'County borders');
  if (topBox.getValue()) {
    Map.addLayer(outline(joined.filter(ee.Filter.eq('top5', 1)), 3), {palette: ['#00bcd4']}, 'Highest-risk counties');
  }
  Map.layers().add(highlight);
  noteLabel.setValue(layer.note);
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
  statusLabel.setValue(selected.name + ' County: loading...');
  detail.clear();
  chartPanel.clear();
  var query = ee.Feature(table.filter(ee.Filter.eq('key', key)).filter(ee.Filter.eq('ym', ym())).first());
  query.toDictionary().evaluate(function (r, err) {
    if (mine !== requestId) { return; }
    if (err || !r) {
      statusLabel.setValue('No prediction found. Check that ASSET_ID points to the uploaded table.');
      return;
    }
    statusLabel.setValue(selected.name + ' County, ' + MONTHS[monthSelect.getValue() - 1] + ' ' + yearSelect.getValue());
    detail.add(section('Prediction'));
    detail.add(row('Chance of any damage', pct(r.p_damage)));
    detail.add(row('Expected loss', usd(r.expected_loss)));
    detail.add(row('Loss if damage occurs', usd(r.loss_if_damage)));
    detail.add(row('Rank in the state', r.rank + ' of ' + N_COUNTIES));
    detail.add(row('Recorded loss (SHELDUS)', r.has_damage ? usd(r.actual_loss) : 'None recorded'));
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
    showRasterMean(mine);
  });

  var rows = table.filter(ee.Filter.eq('key', key)).sort('ym');
  var chart = ui.Chart.feature.byFeature({features: rows, xProperty: 'ym_label',
    yProperties: ['log10_expected_loss', 'log10_actual_loss']})
    .setChartType('LineChart')
    .setOptions({
      title: 'Loss by month (log10 dollars; 3 = $1k, 6 = $1M)',
      legend: {position: 'bottom'},
      hAxis: {showTextEvery: 12, textStyle: {fontSize: 10}},
      vAxis: {viewWindow: {min: 1, max: 8}},
      series: {0: {labelInLegend: 'Predicted expected loss', color: '#e31a1c', lineWidth: 2, pointSize: 0},
               1: {labelInLegend: 'Recorded loss', color: '#3f007d', lineWidth: 0, pointSize: 5}}
    });
  chartPanel.add(chart);
}

// the selected raster's average over the county, when a source layer is on the map
function showRasterMean(mine) {
  var layer = currentLayer();
  // land cover classes and yes/no masks have no meaningful average
  if (layer.type !== 'raster' || layer.classes || layer.unit === 'present') { return; }
  var name = layerSelect.getValue();
  var geometry = counties.filter(ee.Filter.eq('GEOID', selected.geoid)).geometry();
  var image = ee.Image(layer.image(yearSelect.getValue(), monthSelect.getValue())).rename('v');
  image.reduceRegion({reducer: ee.Reducer.mean(), geometry: geometry, scale: layer.scale,
                      bestEffort: true, maxPixels: 1e9}).get('v').evaluate(function (v, err) {
    if (mine !== requestId || err || v === null || v === undefined) { return; }
    detail.insert(0, row('County mean of ' + name, plain(v) + ' ' + layer.unit));
  });
}

Map.onClick(function (coords) {
  statusLabel.setValue('Finding the county...');
  counties.filterBounds(ee.Geometry.Point([coords.lon, coords.lat])).select(['GEOID', 'NAME'])
    .toList(1).evaluate(function (list, err) {
      if (err || !list || !list.length) {
        statusLabel.setValue('Click inside ' + STATE_NAME + '.');
        return;
      }
      var p = list[0].properties;
      selected = {geoid: p.GEOID, name: p.NAME};
      highlight.setEeObject(outline(counties.filter(ee.Filter.eq('GEOID', p.GEOID)), 4));
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

redraw();
