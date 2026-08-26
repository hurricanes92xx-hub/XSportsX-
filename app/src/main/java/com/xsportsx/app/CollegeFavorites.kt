package com.xsportsx.app

/** College teams offered by the My Teams / Favorites picker. */
fun collegeFavoriteTeams(): List<FavoriteTeam> = buildList {
    addAll(collegeTeams("NCAAF", "Football", "Alabama,Arkansas,Auburn,Clemson,Florida,Florida State,Georgia,LSU,Michigan,Michigan State,Notre Dame,Ohio State,Oklahoma,Oklahoma State,Oregon,Penn State,South Carolina,Tennessee,Texas,Texas A&M,USC,Utah,Washington,Wisconsin,Miami,North Carolina,NC State,Virginia Tech,West Virginia,Iowa,Iowa State,Kansas,Kansas State,Missouri,Nebraska,Ole Miss,Mississippi State,TCU,Texas Tech,Baylor,Arizona,Arizona State,Colorado,California,Stanford,UCLA,Utah State,Boise State,Memphis,SMU,Tulane,Appalachian State,James Madison,Liberty"))
    addAll(collegeTeams("NCAAM", "Men's Basketball", "Alabama,Arizona,Auburn,Baylor,Cincinnati,Clemson,Connecticut,Duke,Florida,Florida State,Georgetown,Gonzaga,Houston,Illinois,Indiana,Iowa,Iowa State,Kansas,Kansas State,Kentucky,Louisville,Maryland,Memphis,Michigan,Michigan State,North Carolina,North Carolina State,Notre Dame,Ohio State,Oklahoma,Oklahoma State,Oregon,Penn State,Purdue,Saint Mary's,San Diego State,St. John's,Tennessee,Texas,Texas A&M,Texas Tech,UCLA,USC,Virginia,Virginia Tech,Villanova,Wake Forest,Washington,Wisconsin,Xavier"))
    addAll(collegeTeams("NCAAW", "Women's Basketball", "Alabama,Arizona,Auburn,Baylor,Clemson,Connecticut,Duke,Florida,Florida State,Georgia,Indiana,Iowa,Iowa State,Kansas,Kentucky,Louisville,Maryland,Miami,Michigan,Michigan State,Notre Dame,North Carolina,North Carolina State,Ohio State,Oklahoma,Oregon,South Carolina,Stanford,Tennessee,Texas,Texas A&M,Texas Tech,UCLA,USC,Utah,Villanova,Virginia Tech,Washington,West Virginia,Wisconsin"))
    addAll(collegeTeams("NCAAB", "Baseball", "Arkansas,Auburn,Arizona,Arizona State,California,Clemson,Florida,Florida State,Georgia,LSU,Mississippi State,NC State,North Carolina,Oklahoma,Oklahoma State,Oregon,Oregon State,South Carolina,Stanford,Tennessee,Texas,Texas A&M,TCU,Texas Tech,UCLA,USC,Virginia,Virginia Tech,Wake Forest,Vanderbilt"))
}

private fun collegeTeams(league: String, sport: String, names: String): List<FavoriteTeam> =
    names.split(',').map { name ->
        val n = name.trim()
        FavoriteTeam(n, league, sport, collegeAbbr(n))
    }

private fun collegeAbbr(name: String): String = when (name) {
    "Alabama" -> "ALA"
    "Arizona" -> "ARIZ"
    "Arizona State" -> "ASU"
    "Arkansas" -> "ARK"
    "Auburn" -> "AUB"
    "Baylor" -> "BAY"
    "Boston College" -> "BC"
    "California" -> "CAL"
    "Clemson" -> "CLEM"
    "Connecticut" -> "UCONN"
    "Duke" -> "DUKE"
    "Florida" -> "FLA"
    "Florida State" -> "FSU"
    "Georgia" -> "UGA"
    "Georgetown" -> "GTOWN"
    "Gonzaga" -> "GONZ"
    "Houston" -> "HOU"
    "Illinois" -> "ILL"
    "Indiana" -> "IND"
    "Iowa" -> "IOWA"
    "Iowa State" -> "ISU"
    "Kansas" -> "KU"
    "Kansas State" -> "KSU"
    "Kentucky" -> "UK"
    "LSU" -> "LSU"
    "Louisville" -> "LOU"
    "Maryland" -> "MD"
    "Memphis" -> "MEM"
    "Miami" -> "MIA"
    "Michigan" -> "MICH"
    "Michigan State" -> "MSU"
    "Mississippi State" -> "MSST"
    "Missouri" -> "MIZ"
    "NC State" -> "NCST"
    "Nebraska" -> "NEB"
    "North Carolina" -> "UNC"
    "North Carolina State" -> "NCST"
    "Notre Dame" -> "ND"
    "Ohio State" -> "OSU"
    "Oklahoma" -> "OU"
    "Oklahoma State" -> "OKST"
    "Ole Miss" -> "MISS"
    "Oregon" -> "ORE"
    "Oregon State" -> "ORST"
    "Penn State" -> "PSU"
    "Purdue" -> "PUR"
    "Saint Mary's" -> "SMC"
    "San Diego State" -> "SDSU"
    "SMU" -> "SMU"
    "South Carolina" -> "SCAR"
    "Stanford" -> "STAN"
    "St. John's" -> "SJU"
    "TCU" -> "TCU"
    "Tennessee" -> "TENN"
    "Texas" -> "TEX"
    "Texas A&M" -> "TAMU"
    "Texas Tech" -> "TTU"
    "Tulane" -> "TUL"
    "UCLA" -> "UCLA"
    "USC" -> "USC"
    "Utah" -> "UTAH"
    "Utah State" -> "USU"
    "Virginia" -> "UVA"
    "Virginia Tech" -> "VT"
    "Villanova" -> "NOVA"
    "Wake Forest" -> "WAKE"
    "Washington" -> "WASH"
    "West Virginia" -> "WVU"
    "Wisconsin" -> "WISC"
    else -> name.split(' ').mapNotNull { it.firstOrNull() }.joinToString("").take(4).uppercase()
}
