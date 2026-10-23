"""Export public pipeline outputs for the React app; no credentials are exported.

Run as python -m scripts.export_web_data. Cloudflare only needs the generated
public/data files, so Node-only builds can deploy without installing Python.
"""
import ast
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public' / 'data'


def read(name, parquet=False):
    path = ROOT / 'data_files' / ('parquet' if parquet else 'csv') / (name + ('.parquet' if parquet else '.csv'))
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path) if parquet else pd.read_csv(path)
    for col in ['id', 'match_id', 'player_id', 'team_id', 'home_team_id', 'away_team_id']:
        if col in df:
            df[col] = df[col].astype(str)
    for col in ['kickoff_utc', 'date', 'scraped_at']:
        if col in df:
            df[col] = pd.to_datetime(df[col], utc=True, errors='coerce', format='mixed')
    return df


def records(df):
    return json.loads(df.to_json(orient='records', date_format='iso'))


def export():
    OUT.mkdir(parents=True, exist_ok=True)
    # Refitting is only needed when the actual model inputs change.
    model_input_hash = hashlib.sha256(b''.join((ROOT / 'data_files' / p).read_bytes() if (ROOT / 'data_files' / p).exists() else b'' for p in ['csv/matches.csv', 'parquet/player_match_stats.parquet']) + b''.join((ROOT / p).read_bytes() for p in ['models/dixon_coles.py', 'models/try_scorer.py'])).hexdigest()
    previous_path = OUT / 'snapshot.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
    matches = read('matches').drop_duplicates('id', keep='last')
    players = read('player_match_stats', True)
    # CSV is authoritative, as in utils/cache.py. Normalize join keys first.
    if not players.empty:
        lookup = matches.set_index('id')
        players['league_id'] = players['match_id'].map(lookup['league_id'])
        players['kickoff_utc'] = players['match_id'].map(lookup['kickoff_utc'])
    tables = {'leagues': read('leagues'), 'teams': read('teams'), 'matches': matches,
              'odds': read('odds_snapshots'), 'players': players}
    for key, name in [('standings', 'team_season_stats'), ('elo', 'elo_ratings'),
                      ('predictions', 'precomputed_predictions'), ('bt', 'bradley_terry_ratings'),
                      ('dc_params', 'dc_params')]:
        tables[key] = read(name, True)
    data = {key: records(df) for key, df in tables.items()}
    data['model_input_hash'] = model_input_hash
    # Match pandas' group/sort ordering on the original home leaderboard.
    if not players.empty:
        home_players = players[players.league_id.isin(tables['leagues'].id)]
        home_scorers = home_players.groupby(['player_id', 'player_name', 'team_id'])['tries'].sum().reset_index().sort_values('tries', ascending=False).head(10)
        data['home_scorers'] = records(home_scorers)
    data['generated_at'] = datetime.now(timezone.utc).isoformat()
    data['latest_match_at'] = matches['kickoff_utc'].max().isoformat() if not matches.empty else None
    # Keep the exact Python Dixon-Coles fit available to interactive browser simulations.
    from models import dixon_coles as dc
    final = matches[matches.status == 'final']
    model = previous.get('dc_model') if previous.get('model_input_hash') == model_input_hash else dc.fit(final) if len(final) >= 15 else None
    data['dc_model'] = model
    from utils.venues import VENUE_COORDS
    data['venues'] = VENUE_COORDS
    from models import try_scorer
    data['try_predictions'] = {}
    if previous.get('model_input_hash') == model_input_hash:
        data['try_predictions'] = previous.get('try_predictions', {})
    elif len(final) >= 20 and not players.empty:
        features = try_scorer.build_features(players, matches)
        try_model = try_scorer.train(features)
        for _, fixture in matches[matches.status == 'scheduled'].iterrows():
            scorers = try_scorer.top_try_scorers_for_match(
                fixture.home_team_id, fixture.away_team_id, players, try_model, n=5)
            data['try_predictions'][fixture.id] = records(scorers)
    if model:
        for prediction in data['predictions']:
            result = dc.predict(prediction['home_team_id'], prediction['away_team_id'], model)
            if result:
                prediction.update({f'dc_{key}': result[key] for key in ['p_home', 'p_draw', 'p_away', 'exp_home', 'exp_away']})
    (OUT / 'snapshot.json').write_text(json.dumps(data, allow_nan=False, separators=(',', ':')), encoding='utf-8')
    # Read literal palettes without importing the Streamlit runtime.
    palettes = {}
    tree = ast.parse((ROOT / 'themes.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, 'id', '') in ['_NIGHT_THEMES', '_DAY_THEMES']:
            for key, value in zip(node.value.keys, node.value.values):
                palettes[ast.literal_eval(key)] = {kw.arg: ast.literal_eval(kw.value) for kw in value.keywords}
    (OUT / 'themes.json').write_text(json.dumps(palettes), encoding='utf-8')
    shutil.copyfile(ROOT / 'data_files/logo.png', ROOT / 'public/logo.png')
    print(f'Exported {len(matches)} matches and {len(players)} player records to {OUT}')


if __name__ == '__main__':
    export()
