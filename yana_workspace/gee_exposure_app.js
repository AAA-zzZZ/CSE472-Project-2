// Flood impact app: the model's input layers and predictions for one Midwest state (default Missouri).
// Paste into the Earth Engine Code Editor (https://code.earthengine.google.com) and press Run.
// Pick a state, a layer, a year and a month; click a county to get its mean value.
//
// Layers follow the final variables in yana_workspace/HANDOFF3.md:
//   W same month   monthly rain, wettest 5 days, frost days (PRISM); snowmelt (ERA5-Land)
//   W in advance   root-zone soil moisture and snowpack on day 1 of the month (ERA5-Land)
//   C              10-year 5-day rain level, PRISM 2000-2009 (from the predictions table)
//   X              built-up surface (GHSL), impervious surface (Annual NLCD), land near streams (MERIT HAND)
//   A              wetland share (Annual NLCD)
// Yearly X and A layers show year - 1, the year the model uses.

// ---------- Study area ----------
var STATES = {
  'Missouri (29)': '29', 'Illinois (17)': '17', 'Indiana (18)': '18', 'Iowa (19)': '19',
  'Kansas (20)': '20', 'Michigan (26)': '26', 'Minnesota (27)': '27', 'Nebraska (31)': '31',
  'North Dakota (38)': '38', 'Ohio (39)': '39', 'South Dakota (46)': '46', 'Wisconsin (55)': '55'
};
var ALL_COUNTIES = ee.FeatureCollection('TIGER/2018/Counties');
var counties, region;

function setState(fips) {
  counties = ALL_COUNTIES.filter(ee.Filter.eq('STATEFP', fips));
  region = counties.geometry();
}

// ---------- Model predictions (optional) ----------
// Upload yana_workspace/gee_app/missouri_tester/mo_flood_app_table.csv (from build_app_table.py, the
// same table the flood_explorer_app.js app reads) as a table asset (Assets > NEW > CSV file), then put
// its ID here, e.g. 'projects/flood-513221/assets/mo_flood_app_table'.
// Leave null to show the gridded layers only. Predictions cover the test years 2017-2023.
var PRED_ASSET = null;

// ---------- Helpers ----------
function monthStart(y, m) { return ee.Date.fromYMD(y, m, 1); }

function prismMonth(y, m) {
  var start = monthStart(y, m);
  return ee.ImageCollection('OREGONSTATE/PRISM/ANd').filterDate(start, start.advance(1, 'month'));
}

// GHSL images are 5 years apart: interpolate linearly between the two around the year
function ghslBuilt(y) {
  var lo = Math.min(2020, Math.floor(y / 5) * 5), w = (y - lo) / 5;
  var img = function (e) { return ee.Image('JRC/GHSL/P2023A/GHS_BUILT_S/' + e).select('built_surface'); };
  return img(lo).multiply(1 - w).add(img(lo + 5).multiply(w));
}

function nlcd(id, y) {
  return ee.ImageCollection('projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/' + id)
    .filter(ee.Filter.calendarRange(y, y, 'year')).first().select([0]);
}

// county values from the predictions table, painted as an image
function countyValue(y, m, column) {
  var rows = ee.FeatureCollection(PRED_ASSET)
    .filter(ee.Filter.eq('year', y)).filter(ee.Filter.eq('month', m));
  return counties.map(function (c) {
    // the table keys counties as text 'G' + GEOID, so Earth Engine does not read them as numbers
    var row = rows.filter(ee.Filter.eq('key', ee.String('G').cat(c.get('GEOID'))));
    return c.set('v', ee.Algorithms.If(row.size().gt(0), row.first().get(column), -1));
  }).filter(ee.Filter.gte('v', 0)).reduceToImage(['v'], ee.Reducer.first()).rename('v');
}

// ---------- Layers ----------
// Each entry returns an ee.Image for a year and month, plus display settings.
var LAYERS = {
  'W: monthly rain (PRISM, mm)': {
    image: function (y, m) { return prismMonth(y, m).select('ppt').sum(); },
    vis: {min: 0, max: 250}, note: 'Same-month total (p_month)', scale: 4000
  },
  'W: wettest 5 days (PRISM, mm)': {
    image: function (y, m) {
      var start = monthStart(y, m), days = prismMonth(y, m).select('ppt');
      var n = start.advance(1, 'month').difference(start, 'day');
      // trailing 5-day windows that end on a day of the month, as in w_indices.py's rx5
      var sums = ee.List.sequence(0, n.subtract(1)).map(function (i) {
        var end = start.advance(ee.Number(i).add(1), 'day');
        return ee.ImageCollection('OREGONSTATE/PRISM/ANd').filterDate(end.advance(-5, 'day'), end).select('ppt').sum();
      });
      return ee.ImageCollection.fromImages(sums).max();
    },
    vis: {min: 0, max: 150}, note: 'rx5; the model uses rx5 / 10-year level (rx5_rl_ratio)', scale: 4000
  },
  'W: frost days (PRISM, days)': {
    image: function (y, m) { return prismMonth(y, m).select('tmin').map(function (d) { return d.lt(0); }).sum(); },
    vis: {min: 0, max: 31}, note: 'Days with Tmin below 0 C (frost_days)', scale: 4000
  },
  'W: snowmelt (ERA5-Land, mm)': {
    image: function (y, m) {
      return ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR').filterDate(monthStart(y, m), monthStart(y, m).advance(1, 'month'))
        .first().select('snowmelt_sum').multiply(1000);
    },
    vis: {min: 0, max: 50}, note: 'Same-month total (snowmelt_mm)', scale: 11000
  },
  'W known in advance: root-zone soil moisture (ERA5-Land, m3/m3)': {
    image: function (y, m) {
      var d = ee.Image(ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR').filterDate(monthStart(y, m), monthStart(y, m).advance(1, 'day')).first());
      // depth-weighted 0-100 cm, as in build_panel.py; the model uses its percentile (sm_root_pct)
      return d.select('volumetric_soil_water_layer_1').multiply(7)
        .add(d.select('volumetric_soil_water_layer_2').multiply(21))
        .add(d.select('volumetric_soil_water_layer_3').multiply(72)).divide(100);
    },
    vis: {min: 0.15, max: 0.45}, note: 'Day 1 of the month (sm_root)', scale: 11000
  },
  'W known in advance: snowpack (ERA5-Land, mm water)': {
    image: function (y, m) {
      return ee.Image(ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR').filterDate(monthStart(y, m), monthStart(y, m).advance(1, 'day')).first())
        .select('snow_depth_water_equivalent').multiply(1000);
    },
    vis: {min: 0, max: 100}, note: 'Day 1 of the month (swe_mm)', scale: 11000
  },
  'X: built-up surface (GHSL, m2 per 100 m cell)': {
    image: function (y, m) { return ghslBuilt(y - 1); },
    vis: {min: 0, max: 3000}, note: 'Year - 1, interpolated between 5-year images (log_built_surface)', scale: 100
  },
  'X: impervious surface (Annual NLCD, %)': {
    image: function (y, m) { return nlcd('FRACTIONAL_IMPERVIOUS_SURFACE', y - 1); },
    vis: {min: 0, max: 60}, note: 'Year - 1 (impervious_mean)', scale: 30
  },
  'X: land near streams (MERIT HAND < 5 m)': {
    image: function (y, m) {
      var hnd = ee.Image('MERIT/Hydro/v1_0_1').select('hnd');
      return hnd.lt(5).selfMask().multiply(ee.Image(5).subtract(hnd)); // brighter = lower
    },
    vis: {min: 0, max: 5}, note: 'Static; the model uses the share of land below 5 m (hand_lt5_share)', scale: 90
  },
  'A: wetlands (Annual NLCD classes 90, 95)': {
    image: function (y, m) {
      var lc = nlcd('LANDCOVER', y - 1);
      return lc.eq(90).or(lc.eq(95)).selfMask();
    },
    vis: {min: 0, max: 1}, note: 'Year - 1 (wetland_share)', scale: 30
  }
};

if (PRED_ASSET) {
  LAYERS['C: 10-year 5-day rain level (PRISM 2000-2009, mm)'] = {
    image: function (y, m) { return countyValue(y, m, 'c_rx5_rl10_mm'); },
    vis: {min: 100, max: 200}, note: 'County value used by the model (c_rx5_rl10_mm)', scale: 500, table: true
  };
  LAYERS['W: wettest 5 days / 10-year level'] = {
    image: function (y, m) { return countyValue(y, m, 'rx5_rl_ratio'); },
    vis: {min: 0, max: 1.5}, note: 'County value used by the model (rx5_rl_ratio)', scale: 500, table: true
  };
  LAYERS['Model: P(damage) this month'] = {
    image: function (y, m) { return countyValue(y, m, 'p_damage'); },
    vis: {min: 0, max: 0.5}, note: 'LightGBM hurdle, trained 2000-2016 (build_app_table.py)', scale: 500, table: true
  };
  LAYERS['Model: expected damage this month ($)'] = {
    image: function (y, m) { return countyValue(y, m, 'expected_loss'); },
    vis: {min: 0, max: 500000}, note: 'P(damage) x expected amount, 2024 $', scale: 500, table: true
  };
  LAYERS['SHELDUS: observed property damage ($)'] = {
    image: function (y, m) { return countyValue(y, m, 'actual_loss'); },
    vis: {min: 0, max: 500000}, note: 'Reported property damage, 2024 $ (the outcome)', scale: 500, table: true
  };
}
var PALETTE = ['#000004', '#3b0f70', '#8c2981', '#de4968', '#fe9f6d', '#fcfdbf']; // magma

// ---------- UI ----------
var stateSelect = ui.Select({items: Object.keys(STATES), value: 'Missouri (29)', onChange: function (s) {
  setState(STATES[s]);
  Map.centerObject(counties, 7);
  redraw();
}});
var layerSelect = ui.Select({items: Object.keys(LAYERS), value: Object.keys(LAYERS)[0], onChange: redraw});
var yearSlider = ui.Slider({min: 2000, max: 2023, step: 1, value: 2017, onChange: redraw, style: {stretch: 'horizontal'}});
var monthSlider = ui.Slider({min: 1, max: 12, step: 1, value: 4, onChange: redraw, style: {stretch: 'horizontal'}});
var noteLabel = ui.Label('', {fontSize: '11px', color: 'gray'});
var legend = ui.Panel();
var clickLabel = ui.Label('Click a county to get its mean value.', {whiteSpace: 'pre'});

var panel = ui.Panel({
  widgets: [
    ui.Label('Flood impact model: inputs and predictions', {fontWeight: 'bold', fontSize: '16px'}),
    ui.Label('State'), stateSelect,
    ui.Label('Layer'), layerSelect,
    ui.Label('Year'), yearSlider,
    ui.Label('Month'), monthSlider, noteLabel,
    legend, clickLabel
  ],
  style: {width: '340px', padding: '8px'}
});
ui.root.insert(0, panel);
setState(STATES[stateSelect.getValue()]);
Map.centerObject(counties, 7);
Map.setOptions('HYBRID');

function current() {
  var layer = LAYERS[layerSelect.getValue()];
  return {layer: layer, img: layer.image(yearSlider.getValue(), monthSlider.getValue()).clip(region)};
}

function makeLegend(vis) {
  var bar = ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0),
    params: {bbox: [0, 0, 1, 0.1], dimensions: '200x12', format: 'png', min: 0, max: 1, palette: PALETTE},
    style: {stretch: 'horizontal', maxHeight: '18px', margin: '4px 8px'}
  });
  var labels = ui.Panel(
    [ui.Label(String(vis.min)), ui.Label('', {stretch: 'horizontal'}), ui.Label(String(vis.max))],
    ui.Panel.Layout.flow('horizontal'));
  legend.clear().add(bar).add(labels);
}

function redraw() {
  var c = current();
  Map.layers().reset();
  // gridded layers: mask zeros so the basemap shows where there is nothing; table layers keep zeros
  var shown = c.layer.table ? c.img : c.img.updateMask(c.img.gt(0));
  Map.addLayer(shown, {min: c.layer.vis.min, max: c.layer.vis.max, palette: PALETTE}, layerSelect.getValue());
  var outlines = ee.Image().byte().paint({featureCollection: counties, color: 1, width: 1});
  Map.addLayer(outlines, {palette: ['white']}, 'Counties');
  var y = yearSlider.getValue();
  noteLabel.setValue(c.layer.note + (c.layer.table && (y < 2017) ? '. No predictions before 2017.' : ''));
  makeLegend(c.layer.vis);
}

// click a county: mean of the current layer over that county, plus the model's numbers if loaded
Map.onClick(function (coords) {
  var pt = ee.Geometry.Point([coords.lon, coords.lat]);
  var hit = ee.Feature(counties.filterBounds(pt).first());
  clickLabel.setValue('Computing...');
  var c = current();
  var info = {
    name: hit.get('NAME'), geoid: hit.get('GEOID'),
    mean: c.img.reduceRegion({reducer: ee.Reducer.mean(), geometry: hit.geometry(),
                              scale: c.layer.scale, maxPixels: 1e9, tileScale: 4}).values().get(0)
  };
  if (PRED_ASSET) {
    var row = ee.FeatureCollection(PRED_ASSET)
      .filter(ee.Filter.eq('year', yearSlider.getValue())).filter(ee.Filter.eq('month', monthSlider.getValue()))
      .filter(ee.Filter.eq('key', ee.String('G').cat(hit.get('GEOID'))));
    info.pred = ee.Algorithms.If(row.size().gt(0), ee.Feature(row.first()).toDictionary(), null);
  }
  ee.Dictionary(info).evaluate(function (r, err) {
    if (err || !r) { clickLabel.setValue('Click inside a county of the selected state.'); return; }
    var text = r.name + ' County (' + r.geoid + ') mean: ' + Number(r.mean).toFixed(2);
    if (r.pred) {
      text += '\nP(damage) ' + Number(r.pred.p_damage).toFixed(3) +
              ', expected $' + Math.round(r.pred.expected_loss).toLocaleString() +
              ', observed $' + Math.round(r.pred.actual_loss).toLocaleString();
    }
    clickLabel.setValue(text);
  });
});

redraw();
