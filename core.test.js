import test from "node:test";
import assert from "node:assert/strict";
import { matchScore, rankStreams, similarity } from "./core.js";

test("similarity finds overlapping team names", () => {
  assert(similarity("New York Yankees", "Yankees") > 0);
});

test("matchScore favors both teams", () => {
  const event = {
    title: "Boston Red Sox vs New York Yankees",
    league: "MLB",
    home: {name:"New York Yankees", short:"NYY"},
    away: {name:"Boston Red Sox", short:"BOS"}
  };
  const score = matchScore({name:"MLB BOS NYY", group:"MLB", id:""}, event);
  assert(score >= 50);
});

test("rankStreams puts higher scored streams first", () => {
  const x = rankStreams([{name:"A",score:20},{name:"B",score:90}]);
  assert.equal(x[0].name, "B");
});
