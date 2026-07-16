"""Curated (year, month) pairs with a major, recognizable, dateable event.

Puzzle selection draws from this pool so every edition has a real foothold for
players — instead of a random, obscure "nothing happened" month. The guess range
stays the full 1851-2019; only the *selection* is biased here.

Each entry also carries a KEYWORD HOOK: a "|"-separated set of terms that the
flagship story's front-page headline is likely to contain. The builder uses it
to pull that recognizable story into the four shown (see ranker.find_event_story
and build.build_round), so the event actually surfaces even when the month's raw
front-page volume was dominated by something else. When nothing matches, the
build falls back to the plain ranker — no worse than before.
"""

# (year, month, "event", "headline keyword|hook") — the event text is docs only.
_NOTABLE = [
    (1860, 11, "Lincoln elected", "lincoln|republican triumph"),
    (1861, 4, "Fort Sumter / Civil War begins", "sumter|fort sumter|war begun"),
    (1863, 1, "Emancipation Proclamation", "emancipation|proclamation|slaves"),
    (1863, 7, "Gettysburg", "gettysburg|meade|pennsylvania|invasion"),
    (1865, 4, "Lincoln assassination / war ends", "assassinat|lincoln|booth|surrender|richmond"),
    (1869, 5, "Transcontinental railroad completed", "pacific railroad|promontory|last rail"),
    (1871, 10, "Great Chicago Fire", "chicago"),
    (1876, 6, "Battle of Little Bighorn", "custer|big horn|sioux|massacre"),
    (1881, 7, "Garfield shot", "garfield|guiteau"),
    (1883, 5, "Brooklyn Bridge opens", "brooklyn bridge|east river bridge|great bridge"),
    (1886, 5, "Haymarket affair", "haymarket|anarchist|chicago riot"),
    (1886, 10, "Statue of Liberty dedicated", "bartholdi|statue of liberty|liberty enlightening"),
    (1889, 6, "Johnstown Flood", "johnstown|conemaugh|flood"),
    (1890, 12, "Wounded Knee", "sioux|ghost danc|pine ridge|wounded|big foot"),
    (1892, 1, "Ellis Island opens", "ellis island|immigra"),
    (1898, 2, "USS Maine explodes", "the maine|battleship maine|havana"),
    (1898, 4, "Spanish-American War begins", "spain|spanish|war with spain"),
    (1901, 9, "McKinley assassinated", "mckinley|czolgosz"),
    (1903, 12, "Wright brothers first flight", "wright|flying machine|airship|kitty hawk"),
    (1906, 4, "San Francisco earthquake", "san francisco|earthquake"),
    (1911, 3, "Triangle Shirtwaist fire", "triangle|waist factory|factory fire"),
    (1912, 4, "Titanic sinks", "titanic"),
    (1914, 8, "World War I begins", "war declared|kaiser|belgium|invasion|mobiliz"),
    (1915, 5, "Lusitania sunk", "lusitania"),
    (1917, 4, "US enters World War I", "declaration of war|war with germany|war resolution"),
    (1918, 11, "WWI armistice", "armistice|surrender|kaiser"),
    (1919, 6, "Treaty of Versailles", "peace treaty|versailles|treaty signed"),
    (1920, 1, "Prohibition begins", "prohibition|dry law|liquor"),
    (1920, 8, "19th Amendment ratified", "suffrage|woman suffrage|ratif"),
    (1925, 7, "Scopes trial", "scopes|evolution|dayton"),
    (1927, 5, "Lindbergh crosses the Atlantic", "lindbergh"),
    (1929, 10, "Stock market crash", "stocks|market crash|wall street|selling"),
    (1931, 5, "Empire State Building opens", "empire state"),
    (1932, 11, "FDR elected", "roosevelt"),
    (1933, 3, "FDR inauguration / New Deal", "roosevelt|inaugurat|bank holiday"),
    (1937, 5, "Hindenburg disaster", "hindenburg|zeppelin|dirigible"),
    (1937, 7, "Amelia Earhart disappears", "earhart|aviatrix"),
    (1939, 9, "World War II begins", "poland|hitler|nazi|invasion|war"),
    (1941, 12, "Pearl Harbor", "japan|pearl harbor|hawaii"),
    (1942, 6, "Battle of Midway", "midway"),
    (1944, 6, "D-Day", "invasion|normandy|allies land|beachhead"),
    (1945, 4, "FDR dies / Truman", "roosevelt|truman"),
    (1945, 5, "V-E Day", "germany|surrender|victory|reich|nazi"),
    (1945, 8, "Hiroshima / V-J Day", "atomic|atom bomb|japan|hiroshima|surrender"),
    (1947, 4, "Jackie Robinson debuts", "robinson|dodgers"),
    (1948, 5, "Israel founded", "israel|jewish state|palestine"),
    (1950, 6, "Korean War begins", "korea"),
    (1954, 5, "Brown v. Board of Education", "segregation|desegregat|school ban|court bans"),
    (1955, 12, "Montgomery bus boycott", "montgomery|bus boycott|boycott"),
    (1957, 9, "Little Rock Nine", "little rock|integrat|arkansas"),
    (1957, 10, "Sputnik launched", "satellite|sputnik|red moon"),
    (1959, 1, "Cuban Revolution / Castro", "cuba|castro|batista"),
    (1960, 11, "Kennedy elected", "kennedy"),
    (1961, 4, "Bay of Pigs / Gagarin in space", "cuba|invasion|castro|space man|orbit"),
    (1962, 10, "Cuban Missile Crisis", "cuba|missile|blockade"),
    (1963, 8, "March on Washington", "march on washington|rights march|negroes"),
    (1963, 11, "JFK assassination", "kennedy|assassinat|dallas"),
    (1964, 7, "Civil Rights Act", "rights bill|civil rights|rights act"),
    (1965, 3, "Selma marches", "selma|alabama march|voting rights"),
    (1967, 6, "Six-Day War", "israel|arab|mideast|egypt"),
    (1968, 4, "MLK assassination", "king|memphis|assassinat"),
    (1968, 6, "RFK assassination", "kennedy|shot|assassinat"),
    (1969, 7, "Apollo 11 moon landing", "moon|apollo|astronaut|lunar"),
    (1969, 8, "Woodstock", "woodstock|festival|rock fair"),
    (1970, 4, "Apollo 13", "apollo|astronaut|spacemen|crippled"),
    (1970, 5, "Kent State", "kent state|students slain|guardsmen|campus"),
    (1972, 6, "Watergate break-in", "watergate|democratic headquarters|bugging"),
    (1973, 1, "Roe v. Wade / Vietnam ceasefire", "abortion|vietnam|cease-fire|truce"),
    (1974, 8, "Nixon resigns", "nixon|resign|impeach"),
    (1975, 4, "Fall of Saigon", "saigon|vietnam|evacuat"),
    (1976, 7, "US Bicentennial", "bicentennial|fourth of july"),
    (1977, 8, "Elvis dies", "presley|elvis"),
    (1978, 9, "Camp David Accords", "camp david|sadat|begin|mideast"),
    (1979, 3, "Three Mile Island", "nuclear|reactor|harrisburg|radiation"),
    (1979, 11, "Iran hostage crisis", "iran|hostage|tehran|embassy"),
    (1980, 12, "John Lennon killed", "lennon|beatle"),
    (1981, 3, "Reagan shot", "reagan|shot|wounded"),
    (1986, 1, "Challenger disaster", "shuttle|challenger|astronaut"),
    (1986, 4, "Chernobyl", "chernobyl|soviet nuclear|reactor|radiation"),
    (1987, 10, "Black Monday crash", "stocks|market|dow|plunge"),
    (1989, 11, "Berlin Wall falls", "berlin|wall|east germ"),
    (1990, 8, "Iraq invades Kuwait", "iraq|kuwait|hussein"),
    (1991, 1, "Gulf War begins", "iraq|baghdad|gulf war|allies attack"),
    (1991, 12, "Soviet Union dissolves", "soviet|gorbachev|yeltsin"),
    (1992, 4, "Los Angeles riots", "los angeles|riot|king verdict"),
    (1993, 2, "World Trade Center bombing", "trade center|bomb|blast"),
    (1995, 4, "Oklahoma City bombing", "oklahoma|bomb|blast"),
    (1997, 8, "Princess Diana dies", "diana|princess"),
    (1998, 12, "Clinton impeachment", "clinton|impeach"),
    (1999, 4, "Columbine", "colorado|school|littleton|shooting"),
    (2000, 11, "Bush v. Gore election", "florida|recount|bush|gore"),
    (2001, 9, "September 11 attacks", "attack|towers|trade center|terror|hijack"),
    (2003, 3, "Iraq War begins", "iraq|baghdad|war begins"),
    (2004, 12, "Indian Ocean tsunami", "tsunami|tidal wave|catastrophe in asia"),
    (2005, 8, "Hurricane Katrina", "katrina|new orleans|hurricane"),
    (2008, 9, "Financial crisis / Lehman", "lehman|wall street|bailout|crisis"),
    (2008, 11, "Obama elected", "obama"),
    (2009, 1, "Obama inauguration", "obama|inaugurat"),
    (2010, 4, "Deepwater Horizon", "oil spill|oil rig|deepwater|gulf spill|drilling rig"),
    (2011, 5, "Bin Laden killed", "bin laden|qaeda"),
    (2012, 10, "Hurricane Sandy", "sandy|storm|hurricane"),
    (2013, 4, "Boston Marathon bombing", "boston|marathon|bomb"),
    (2015, 6, "Same-sex marriage legalized", "marriage|gay|same-sex"),
    (2016, 11, "Trump elected", "trump"),
    (2017, 1, "Trump inauguration", "trump|inaugurat"),
]

# The selectable pool: just the (year, month) pairs.
NOTABLE = [(y, m) for (y, m, _event, _kw) in _NOTABLE]

# Flagship-story keyword hook per month, for build.build_round's force-include.
EVENT_KEYWORDS = {(y, m): kw for (y, m, _event, kw) in _NOTABLE}

# Human-readable event label per month (docs / logging).
EVENT_LABEL = {(y, m): event for (y, m, event, _kw) in _NOTABLE}
