"""Build a fake season + fake entries so the pipeline can be exercised offline."""
import csv, json, random
from pathlib import Path

PL = ["Liverpool","Arsenal","Man City","Chelsea","Newcastle","Aston Villa","Man United",
      "Tottenham","Brighton","Bournemouth","Crystal Palace","Fulham","Everton","Brentford",
      "West Ham","Nottingham Forest","Wolves","Leeds","Sunderland","Burnley"]
CH = ["Ipswich","Southampton","Leicester","Coventry","Birmingham","West Brom","Middlesbrough"]
PLAYERS = {"Haaland":"Man City","Salah":"Liverpool","Isak":"Newcastle","Palmer":"Chelsea",
           "Watkins":"Aston Villa","Saka":"Arsenal","Wirtz":"Liverpool","Mateta":"Crystal Palace",
           "Bowen":"West Ham","Mitoma":"Brighton","Cunha":"Man United","Schade":"Brentford"}

Path("cache").mkdir(exist_ok=True)
def standings(teams):
    return {"standings":[{"type":"TOTAL","table":[
        {"position":i+1,"team":{"name":t+" FC","shortName":t}} for i,t in enumerate(teams)]}]}
json.dump(standings(PL), open("cache/standings_PL.json","w"))
json.dump(standings(CH), open("cache/standings_ELC.json","w"))

random.seed(7)
clubs = sorted({c for c in PLAYERS.values()})
json.dump({
  "teams":[{"id":i,"name":c} for i,c in enumerate(clubs)],
  "elements":[{"web_name":p,"team":clubs.index(c),
               "goals_scored":random.randint(0,14),"own_goals":0}
              for p,c in PLAYERS.items()],
}, open("cache/fpl_bootstrap.json","w"))

HEADERS = ["Timestamp","Your name",
  "PL top 6 - 1st","PL top 6 - 2nd","PL top 6 - 3rd","PL top 6 - 4th","PL top 6 - 5th","PL top 6 - 6th",
  "PL bottom 3 - 18th","PL bottom 3 - 19th","PL bottom 3 - 20th",
  "Championship - 1st","Championship - 2nd","Championship - play-off winner",
  "PL top scorer","PL Players' Player of the Year","PL Young Player of the Year",
  "FA Cup winner","Carabao Cup winner","Champions League winner",
  "Europa League winner","Conference League winner",
  "First PL manager out","Blackjack - player 1","Blackjack - player 2","Blackjack - player 3"]

names = ["Jack the builder","Linky","Ginger L.","Deano","Wivvy","Spanky","Shady","Clarkey","Gilly","Cookey"]
rows=[]
for n in names:
    t6 = random.sample(PL[:9],6); b3 = random.sample(PL[-6:],3)
    ch = random.sample(CH[:5],3)
    bj = random.sample([p for p in PLAYERS],3)
    rows.append(["2026-08-01", n, *t6, *b3, *ch,
        random.choice(list(PLAYERS)), random.choice(list(PLAYERS)), random.choice(list(PLAYERS)),
        random.choice(PL[:8]), random.choice(PL[:8]), random.choice(["Real Madrid","Barcelona","PSG"]),
        random.choice(["Roma","Aston Villa"]), random.choice(["Fiorentina","Crystal Palace"]),
        random.choice(["Scott Parker","D. Farke","Keith Andrews"]), *bj])
with open("data/predictions.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(HEADERS); w.writerows(rows)
print("fixtures written")
