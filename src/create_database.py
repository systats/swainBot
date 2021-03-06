import sqlite3
import json
from query_wiki import query_wiki
from champion_info import champion_id_from_name, champion_name_from_id, convert_champion_alias, AliasException
import re
import pandas as pd
import draft_db_ops as dbo

def table_col_info(cursor, tableName, printOut=False):
    """
    Returns a list of tuples with column informations:
    (id, name, type, notnull, default_value, primary_key)
    """
    cursor.execute('PRAGMA TABLE_INFO({})'.format(tableName))
    info = cursor.fetchall()

    if printOut:
        print("Column Info:\nID, Name, Type, NotNull, DefaultVal, PrimaryKey")
        for col in info:
            print(col)
    return info

def create_tables(cursor, tableNames, columnInfo, clobber = False):
    """
    create_tables attempts to create a table for each table in the list tableNames with
    columns as defined by columnInfo. For each if table = tableNames[k] then the columns for
    table are defined by columns = columnInfo[k]. Note that each element in columnInfo must
    be a list of strings of the form column[j] = "jth_column_name jth_column_data_type"

    Args:
        cursor (sqlite cursor): cursor used to execute commmands
        tableNames (list(string)): string labels for tableNames
        columnInfo (list(list(string))): list of string labels for each column of each table
        clobber (bool): flag to determine if old tables should be overwritten

    Returns:
        status (int): 0 if table creation failed, 1 if table creation was successful
    """

    for (table, colInfo) in zip(tableNames, columnInfo):
        columnInfoString = ", ".join(colInfo)
        try:
            if clobber:
                cur.execute("DROP TABLE IF EXISTS {tableName}".format(tableName=table))
            cur.execute("CREATE TABLE {tableName} ({columnInfo})".format(tableName=table,columnInfo=columnInfoString))
        except:
            print("Table {} already exists! Here's it's column info:".format(table))
            table_col_info(cursor, table, True)
            print("***")
            return 0

    return 1

if __name__ == "__main__":
    dbName = "competitiveGameData.db"
    tableNames = ["game", "pick", "ban", "team"]

    columnInfo = []
    # Game table columns
    columnInfo.append(["id INTEGER PRIMARY KEY",
                        "tournament TEXT","tourn_game_id INTEGER", "week INTEGER", "patch TEXT",
                        "blue_teamid INTEGER NOT NULL", "red_teamid INTEGER NOT NULL",
                        "winning_team INTEGER"])
    # Pick table columns
    columnInfo.append(["id INTEGER PRIMARY KEY",
                        "game_id INTEGER", "champion_id INTEGER","position_id INTEGER",
                        "selection_order INTEGER", "side_id INTEGER"])
    # Ban table columns
    columnInfo.append(["id INTEGER PRIMARY KEY",
                        "game_id INTEGER", "champion_id INTEGER", "selection_order INTEGER", "side_id INTEGER"])
    # Team table columns
    columnInfo.append(["id INTEGER PRIMARY KEY",
                        "region TEXT", "display_name TEXT"])

    conn = sqlite3.connect("tmp/"+dbName)
    cur = conn.cursor()
    print("Creating tables..")
    create_tables(cur, tableNames, columnInfo, clobber = True)

    year = "2018"
    regions = ["EU_LCS","NA_LCS","LPL","LMS","LCK", "NA_ACA", "KR_CHAL"]
    tournaments = ["Spring_Season"]
    for region in regions:
        for tournament in tournaments:
            skip_commit = False
            print("Querying: {}".format(year+"/"+region+"/"+tournament))
            gameData = query_wiki(year, region, tournament)
            for game in gameData:
                seen_bans = set()
                print("Week {}, patch {}, {} v {}".format(game["week"], game["patch"], game["blue_team"], game["red_team"]))
                bans = game["bans"]["blue"] + game["bans"]["red"]
                for ban in bans:
                    if ban not in seen_bans:
                        seen_bans.add(ban)
                    else:
                        print(" Duplicate ban found! {}".format(ban))
                        print("  ".format(seen_bans))
                        if(ban != "none"):
                            skip_commit = True

                seen_picks = set()
                for side in ["blue", "red"]:
                    seen_positions = set()
                    for pick in game["picks"][side]:
                        (p,pos) = pick
                        if p not in seen_picks:
                            seen_picks.add(p)
                        else:
                            print("  Duplicate pick found! {}".format(p))
                            print("  {}".format(seen_picks))
                            skip_commit = True

                        if pos not in seen_positions:
                            seen_positions.add(pos)
                        else:
                            print("   Duplicate pos found! {}".format(pos))
                            print("  {}".format(seen_positions))
                            skip_commit = True

            if(not skip_commit):
                print("Attempting to insert {} games..".format(len(gameData)))
                status = dbo.insert_team(cur,gameData)
                status = dbo.insert_game(cur,gameData)
                status = dbo.insert_ban(cur,gameData)
                status = dbo.insert_pick(cur,gameData)
                print("Committing changes to db..")
                conn.commit()
            else:
                print("errors found.. skipping commit")

#    print(json.dumps(game, indent=4, sort_keys=True))

    year = "2018"
    region = "International"
    tournaments = []

    for tournament in tournaments:
        print("Querying: {}".format("/".join([year, region, tournament])))
        gameData = query_wiki(year, region, tournament)
        for game in gameData:
            print(game["tourn_game_id"])
            seen_bans = set()
            print("{} v {}".format(game["blue_team"], game["red_team"]))
            bans = game["bans"]["blue"] + game["bans"]["red"]
            for ban in bans:
                if ban not in seen_bans:
                    seen_bans.add(ban)
                else:
                    print(" Duplicate ban found! {}".format(ban))
                    print("  ".format(seen_bans))

            seen_picks = set()
            for side in ["blue", "red"]:
                seen_positions = set()
                for pick in game["picks"][side]:
                    (p,pos) = pick
                    if p not in seen_picks:
                        seen_picks.add(p)
                    else:
                        print("  Duplicate pick found! {}".format(p))
                        print("  ".format(seen_picks))

                    if pos not in seen_positions:
                        seen_positions.add(pos)
                    else:
                        print("   Duplicate pos found! {}".format(pos))
                        print("  ".format(seen_positions))
        print("Attempting to insert {} games..".format(len(gameData)))
        status = dbo.insert_team(cur,gameData)
        status = dbo.insert_game(cur,gameData)
        status = dbo.insert_ban(cur,gameData)
        status = dbo.insert_pick(cur,gameData)
        print("Committing changes to db..")
        conn.commit()

    query = (
    "SELECT game_id, champion_id, selection_order, side_id"
    "  FROM ban"
    " WHERE game_id = 1 AND side_id = 0"
    )
    df = pd.read_sql_query(query, conn)
    #print(df)

#    query = ("SELECT game.tournament, game.tourn_game_id, blue.team, red.team, ban.side_id,"
#             "       ban.champion_id AS champ, ban.selection_order AS ord"
#             "  FROM (game "
#             "       JOIN (SELECT id, display_name as team FROM team) AS blue"
#             "         ON game.blue_teamid = blue.id)"
#             "       JOIN (SELECT id, display_name as team FROM team) AS red"
#             "         ON game.red_teamid = red.id"
#             "  LEFT JOIN (SELECT game_id, side_id, champion_id, selection_order FROM ban) AS ban"
#             "         ON game.id = ban.game_id"
#             "  WHERE game.id IN (SELECT game_id FROM ban WHERE champion_id IS ?)")
#    params = (None,)
#    db = pd.read_sql_query(query, conn, params=params)
#    print(db)

    print("***")
    gameIds = dbo.get_game_ids_by_tournament(cur, "2018/EU/Spring_Season")
    for i in gameIds:
        match = dbo.get_match_data(cur, i)
        print("Week {}, patch {}: {} vs {}".format(match["week"], match["patch"], match["blue_team"],match["red_team"]))
    print("Closing db..")
    conn.close()
