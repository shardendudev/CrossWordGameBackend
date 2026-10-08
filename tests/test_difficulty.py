import pytest
from app.engine.difficulty import calculateBaseDifficulty

@pytest.mark.parametrize("kwargs",[{},
{"imdbVotes":0,"imdbRating":0,"budget":0,"revenue":0, "awardsSummary":"","lowContext":True},
{"imdbVotes":5000000,"imdbRating":10.0,"budget":1000000,"revenue":3000000000},
{"imdbVotes":-50,"imdbRating":-2.0,"budget":-100},
{"imdbVotes":250000,"imdbRating":7.5}])
def test_boundedness_and_default_values(kwargs):
    result = calculateBaseDifficulty(**kwargs)

    print(result)
    assert isinstance(result,float)

    assert 0.0 <= result <= 1.0


def test_difficulty_for_extremes():
    blockbuster_args = {"imdbVotes":2500000,"imdbRating":9.0,"revenue":2000000000,"awardsSummary":"Won 3 Oscars","lowContext":False}
    indie_args = {"imdbVotes":50,"imdbRating":4.0,"budget":0,"revenue":0,"awardsSummary":"","lowContext":True}
    blockbuster_diff = calculateBaseDifficulty(**blockbuster_args)
    indie_diff = calculateBaseDifficulty(**indie_args)

    print(blockbuster_diff,indie_diff)
    assert blockbuster_diff < indie_diff
    assert blockbuster_diff < 0.20
    assert indie_diff > 0.85



def test_feature_sensitivity():
    baseline = {"imdbVotes": 50_000, "imdbRating": 7.0, "revenue": 50_000_000}
    lowVote_diff = calculateBaseDifficulty(imdbVotes=1000)
    highVote_diff = calculateBaseDifficulty(imdbVotes=500000)
    print(lowVote_diff,highVote_diff)
    assert highVote_diff < lowVote_diff

    no_awards_diff = calculateBaseDifficulty(**baseline,awardsSummary="")
    high_awards_diff = calculateBaseDifficulty(**baseline,awardsSummary="Won 10 Oscars")
    print(no_awards_diff,high_awards_diff)

    assert no_awards_diff > high_awards_diff

    low_context_diff = calculateBaseDifficulty(**baseline,lowContext=True)
    high_context_diff = calculateBaseDifficulty(**baseline,lowContext=False)

    print(low_context_diff, high_context_diff)
    assert low_context_diff > high_context_diff

    baselineCommercial = {"imdbVotes":50000, "imdbRating":7.0, "year":1960  }

    low_commercial_diff = calculateBaseDifficulty(**baselineCommercial, revenue=0, budget=0)
    high_commercial_diff = calculateBaseDifficulty(**baselineCommercial, revenue=100000000, budget=50000000)

    print(low_commercial_diff, high_commercial_diff)
    assert low_commercial_diff > high_commercial_diff