import express from "express";
import { getEvents, streamsFor, newsStreamsForChannel, providerStatus } from "./providers.js";
import { TTLCache } from "./core.js";
import { leagueVisual, gameVisual } from "./visuals.js";
import { artworkForEvent, artworkForLeague } from "./artwork.js";
import { installNuvioArtwork } from "./nuvio-artwork-middleware.js";
import { enrichNcaafEvents, cfpWatchEvents, cfpWatchMeta } from "./cfp-watch.js";
import fs from "node:fs";
import path from "node:path";

const app = express();
installNuvioArtwork(app);
const PORT = Number(process.env.PORT || 7000);
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;
const cache = new TTLCache();
const EVENT_REFRESH_MS = Number(process.env.EVENT_REFRESH_MS || 30000);
const DEFAULT_TZ = process.env.DEFAULT_TIMEZONE || "UTC";
const APP_VERSION = "4.4.0";
let eventRefreshPromise = null;

const LEAGUES = [
  ["nfl","NFL","football","nfl.gif"],["nba","NBA","basketball","nba.gif"],["nhl","NHL","hockey","nhl.gif"],["mlb","MLB","baseball","mlb.gif"],
  ["ncaaf","NCAA Football","football","ncaaf.gif"],["ncaab","NCAA Basketball","basketball","ncaab.gif"],["wnba","WNBA","basketball","wnba.gif"],["mls","MLS","soccer","mls.gif"],
  ["premier-league","Premier League","soccer","premier-league.gif"],["la-liga","La Liga","soccer","la-liga.gif"],["f1","Formula 1","racing","f1.gif"],["motogp","MotoGP","racing","motogp.gif"],
  ["ufc","UFC","mma","ufc.gif"],["boxing","Boxing","boxing","boxing.gif"],["atp","ATP Tennis","tennis","atp.gif"],["wta","WTA Tennis","tennis","wta.gif"],
  ["pga","PGA Golf","golf","pga.gif"],["rugby","Rugby","rugby","rugby.gif"],["cricket","Cricket","cricket","cricket.gif"],["pdc","Darts","darts","pdc.gif"],["afl","AFL","football","afl.gif"]
].map(([id,name,sport,asset]) => ({ id, name, sport, asset }));
const leagueMap = new Map(LEAGUES.map(x => [x.id, x]));

const FAVORITE_TEAMS = [