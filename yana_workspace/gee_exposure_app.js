// Exposure heatmap app: Washington County, OH (39167) and its four Ohio neighbours.
// Paste into the Earth Engine Code Editor (https://code.earthengine.google.com) and press Run.
// Pick an exposure layer and a year; click a county to get its mean value.

// ---------- Study area ----------
var GEOIDS = ['39167', '39009', '39111', '39115', '39121'];
var counties = ee.FeatureCollection('TIGER/2018/Counties')
  .filter(ee.Filter.inList('GEOID', GEOIDS));
var focus = counties.filter(ee.Filter.eq('GEOID', '39167'));
var region = counties.geometry();

// ---------- Exposure layers ----------
// Each entry returns an ee.Image for a given year, plus display settings.
var LAYERS = {
  'Built-up surface (GHSL, m² per 100 m cell)': {
    // GHSL epochs are every 5 years, so snap the year to the nearest epoch
    image: function (y) {
      var epoch = Math.min(2020, Math.round(y / 5) * 5);
      return ee.ImageCollection('JRC/GHSL/P2023A/GHS_BUILT_S')
        .filter(ee.Filter.calendarRange(epoch, epoch, 'year')).first()
        .select('built_surface');
    },
    vis: {min: 0, max: 3000}, note: 'GHSL epoch nearest the year (5-year steps)', scale: 100
  },
  'Population (GHSL, people per 100 m cell)': {
    image: function (y) {
      var epoch = Math.min(2020, Math.round(y / 5) * 5);
      return ee.ImageCollection('JRC/GHSL/P2023A/GHS_POP')
        .filter(ee.Filter.calendarRange(epoch, epoch, 'year')).first()
        .select('population_count');
    },
    vis: {min: 0, max: 50}, note: 'GHSL epoch nearest the year (5-year steps)', scale: 100
  },
  'Population (WorldPop, people per 100 m cell)': {
    image: function (y) {
      return ee.ImageCollection('WorldPop/GP/100m/pop')
        .filter(ee.Filter.eq('country', 'USA'))
        .filter(ee.Filter.eq('year', Math.min(2020, y))).mosaic()
        .select('population');
    },
    vis: {min: 0, max: 20}, note: 'Annual, 2000-2020 (later years show 2020)', scale: 100
  },
  'Impervious surface (Annual NLCD, %)': {
    image: function (y) {
      return ee.ImageCollection('projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/FRACTIONAL_IMPERVIOUS_SURFACE')
        .filter(ee.Filter.calendarRange(y, y, 'year')).first().select([0]);
    },
    vis: {min: 0, max: 60}, note: 'Annual, 1985-2023', scale: 30
  },
  'Low land near streams (MERIT HAND < 5 m)': {
    image: function (y) {
      var hnd = ee.Image('MERIT/Hydro/v1_0_1').select('hnd');
      return hnd.lt(5).selfMask().multiply(ee.Image(5).subtract(hnd)); // deeper = lower
    },
    vis: {min: 0, max: 5}, note: 'Static; brighter = closer to stream level (m)', scale: 90
  },
  'Surface water occurrence (JRC, % of time)': {
    image: function (y) {
      return ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence');
    },
    vis: {min: 0, max: 100}, note: 'Static, 1984-2021', scale: 30
  }
};

// ---------- Model predictions (optional) ----------
// Upload yana_workspace/results/predictions_5county.csv as a table asset (Assets > NEW > CSV),
// then put its ID here, e.g. 'projects/cse472-project-2/assets/predictions_5county'.
// Leave null to show exposure layers only. Predictions cover 2010-2023.
var PRED_ASSET = null;

function countyValue(y, column, reducer) {
  var rows = ee.FeatureCollection(PRED_ASSET).filter(ee.Filter.eq('year', y));
  return counties.map(function (c) {
    var g = ee.String(c.get('GEOID'));
    // the CSV upload may store GEOID as a number, so match either form
    var mine = rows.filter(ee.Filter.or(ee.Filter.eq('GEOID', g), ee.Filter.eq('GEOID', ee.Number.parse(g))));
    return c.set('v', reducer === 'sum' ? mine.aggregate_sum(column) : mine.aggregate_mean(column));
  }).reduceToImage(['v'], ee.Reducer.first()).rename('v');
}

if (PRED_ASSET) {
  LAYERS['Model: mean monthly P(damage)'] = {
    image: function (y) { return countyValue(y, 'p_damage', 'mean'); },
    vis: {min: 0, max: 0.6}, note: 'Hurdle model (own + neighbour hazard), trained 2010-2018', scale: 500
  };
  LAYERS['Model: expected damage in year ($)'] = {
    image: function (y) { return countyValue(y, 'expected_dmg', 'sum'); },
    vis: {min: 0, max: 2000000}, note: 'Sum of monthly expected loss, 2024 $', scale: 500
  };
  LAYERS['SHELDUS: observed damage months'] = {
    image: function (y) { return countyValue(y, 'has_damage', 'sum'); },
    vis: {min: 0, max: 6}, note: 'Months with reported property damage (SHELDUS)', scale: 500
  };
}
var PALETTE = ['#000004', '#3b0f70', '#8c2981', '#de4968', '#fe9f6d', '#fcfdbf']; // magma

// ---------- UI ----------
var layerSelect = ui.Select({items: Object.keys(LAYERS), value: Object.keys(LAYERS)[0], onChange: redraw});
var yearSlider = ui.Slider({min: 2000, max: 2023, step: 1, value: 2020, onChange: redraw, style: {stretch: 'horizontal'}});
var noteLabel = ui.Label('', {fontSize: '11px', color: 'gray'});
var legend = ui.Panel();
var clickLabel = ui.Label('Click a county to get its mean value.');

var panel = ui.Panel({
  widgets: [
    ui.Label('Flood exposure: Washington Co., OH', {fontWeight: 'bold', fontSize: '16px'}),
    ui.Label('Exposure layer'), layerSelect,
    ui.Label('Year'), yearSlider, noteLabel,
    legend, clickLabel
  ],
  style: {width: '320px', padding: '8px'}
});
ui.root.insert(0, panel);
Map.centerObject(counties, 9);
Map.setOptions('HYBRID');

function current() {
  var layer = LAYERS[layerSelect.getValue()];
  return {layer: layer, img: layer.image(yearSlider.getValue()).clip(region)};
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
  // mask zeros so the basemap shows where there is no exposure
  Map.addLayer(c.img.updateMask(c.img.gt(0)),
               {min: c.layer.vis.min, max: c.layer.vis.max, palette: PALETTE},
               layerSelect.getValue());
  var outlines = ee.Image().byte().paint({featureCollection: counties, color: 1, width: 1});
  var focusLine = ee.Image().byte().paint({featureCollection: focus, color: 1, width: 3});
  Map.addLayer(outlines, {palette: ['white']}, 'Counties');
  Map.addLayer(focusLine, {palette: ['cyan']}, 'Washington (focus)');
  noteLabel.setValue(c.layer.note);
  makeLegend(c.layer.vis);
}

// click a county: mean of the current layer over that county
Map.onClick(function (coords) {
  var pt = ee.Geometry.Point([coords.lon, coords.lat]);
  var hit = counties.filterBounds(pt).first();
  clickLabel.setValue('Computing...');
  var c = current();
  ee.Dictionary({
    name: ee.Feature(hit).get('NAME'),
    mean: c.img.reduceRegion({reducer: ee.Reducer.mean(), geometry: ee.Feature(hit).geometry(),
                              scale: c.layer.scale, maxPixels: 1e9}).values().get(0)
  }).evaluate(function (r, err) {
    if (err || !r) { clickLabel.setValue('Click inside one of the 5 counties.'); return; }
    clickLabel.setValue(r.name + ' County mean: ' + Number(r.mean).toFixed(2));
  });
});

redraw();
