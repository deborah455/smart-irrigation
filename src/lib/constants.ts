export const REGION_TOGGLES = {
  asal:     { use_humidity: 0, use_wind: 0, use_leaf_wetness: 0 },
  coastal:  { use_humidity: 1, use_wind: 0, use_leaf_wetness: 1 },
  highlands:{ use_humidity: 1, use_wind: 0, use_leaf_wetness: 0 },
  western:  { use_humidity: 1, use_wind: 0, use_leaf_wetness: 0 },
  rift:     { use_humidity: 1, use_wind: 1, use_leaf_wetness: 0 },
} as const;

export const REGION_CENTROIDS = {
  asal:     { lat: -1.8, lon: 37.6 },
  coastal:  { lat: -4.0, lon: 39.7 },
  highlands:{ lat: -0.4, lon: 36.9 },
  western:  { lat:  0.3, lon: 34.8 },
  rift:     { lat:  0.1, lon: 35.3 },
} as const;

export const CROP_FEATURES: Record<string,{core:string[]; optional:string[]}> = {
  maize:{core:["soil_moisture_top"],optional:["flow_lpm","leaf_wetness","soil_ec"]},
  beans:{core:["soil_moisture_top"],optional:["leaf_wetness","flow_lpm"]},
  cowpea:{core:["soil_moisture_top"],optional:["soil_ec"]},
  sorghum:{core:["soil_moisture_deep"],optional:["soil_ec"]},
  millet:{core:["soil_moisture_top"],optional:[]},
  wheat:{core:["soil_moisture_deep"],optional:[]},
  barley:{core:["soil_moisture_deep"],optional:[]},
  rice:{core:["flow_lpm"],optional:["soil_moisture_top"]},
  potato:{core:["soil_moisture_top"],optional:["leaf_wetness","flow_lpm","soil_ec"]},
  sweet_potato:{core:["soil_moisture_top"],optional:[]},
  cassava:{core:["soil_moisture_deep"],optional:[]},
  tomato:{core:["soil_moisture_top","leaf_wetness"],optional:["flow_lpm","soil_ec"]},
  onion:{core:["soil_moisture_top","leaf_wetness"],optional:[]},
  cabbage:{core:["soil_moisture_top","leaf_wetness"],optional:[]},
  kale:{core:["soil_moisture_top","leaf_wetness"],optional:[]},
  spinach:{core:["soil_moisture_top","leaf_wetness"],optional:[]},
  capsicum:{core:["soil_moisture_top","leaf_wetness"],optional:[]},
  banana:{core:["soil_moisture_deep"],optional:["flow_lpm"]},
  coffee:{core:["soil_moisture_deep"],optional:[]},
  tea:{core:["soil_moisture_top"],optional:[]},
  sugarcane:{core:["soil_moisture_deep"],optional:[]},
  pineapple:{core:["soil_moisture_top"],optional:[]},
  mango:{core:["soil_moisture_deep"],optional:[]},
  avocado:{core:["soil_moisture_deep"],optional:[]},
  sunflower:{core:["soil_moisture_deep"],optional:[]},
  groundnut:{core:["soil_moisture_top"],optional:[]},
  cotton:{core:["soil_moisture_deep"],optional:[]},
  watermelon:{core:["soil_moisture_top"],optional:["leaf_wetness"]},
};

export const FARMER_FIELDS: Record<string, {label:string; min:number; max:number; step:number; default:number}> = {
  soil_moisture_top:{label:"Top soil moisture (0..1)",min:0,max:1,step:0.01,default:0.18},
  soil_moisture_deep:{label:"Deep soil moisture (0..1)",min:0,max:1,step:0.01,default:0.22},
  leaf_wetness:{label:"Leaf wetness (0 or 1)",min:0,max:1,step:1,default:0},
  flow_lpm:{label:"Irrigation flow yesterday (L/min)",min:0,max:10,step:0.1,default:0.1},
  soil_ec:{label:"Soil EC / salinity (dS/m)",min:0,max:5,step:0.1,default:0.6},
  days_since_last_irrig:{label:"Days since last irrigation",min:0,max:30,step:1,default:1},
  area_m2:{label:"Plot area (m²)",min:10,max:100000,step:10,default:400},
};
