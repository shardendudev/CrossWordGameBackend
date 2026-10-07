import sys
import os
import math
import re
import asyncio
import argparse
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func, desc, asc
from app.db.session import AsyncSessionLocal
from app.db.models.movie import Movie

def calculate_exact_image_formula(
    imdb_votes: int = 0,
    imdb_rating: float = 0.0,
    budget: int = 0,
    revenue: int = 0,
    awards_summary: str = "",
    low_context: bool = False,
    votes_min: int = 100,
    votes_max: int = 2_500_000,
) -> dict:
    """
    D_base = 1.0 - min(1.0, [w_v * V_norm + w_r * R_norm + w_b * B_norm + w_a * A_bonus - P_context])
    """
    # 1. Logarithmic Vote Volume (V_norm)
    # V_norm = (log10(imdb_votes + 1) - log10(votes_min + 1)) / (log10(votes_max + 1) - log10(votes_min + 1))
    v = (imdb_votes or 0)
    v_norm = (math.log10(v + 1) - math.log10(votes_min + 1)) / (
        math.log10(votes_max + 1) - math.log10(votes_min + 1)
    )

    # 2. Box Office Commercial Impact (B_norm)
    # B_norm = log10(max(revenue, budget) + 1) / log10(3_000_000_000 + 1)
    comm = max(revenue or 0, budget or 0)
    b_norm = math.log10(comm + 1) / math.log10(3_000_000_000 + 1)

    # 3. Critical Acclaim (R_norm)
    # R_norm = imdb_rating / 10.0
    r_norm = (imdb_rating or 0.0) / 10.0

    # 4. Awards & Cultural Legacy Bonus (A_bonus)
    # 0.10 if won Oscar / Academy Award / Palme d'Or / BAFTA / major win
    # 0.05 if nominations or major regional wins
    # 0.00 otherwise
    a_bonus = 0.00
    if awards_summary:
        text_lower = awards_summary.lower()
        top_win_patterns = [
            r"won\s+.*?(?:academy\s+award|oscar|palme\s+d'or)",
            r"(?:academy\s+award|oscar|palme\s+d'or)\s+winner",
        ]
        nomination_patterns = [
            r"nominat",
            r"golden\s+globe",
            r"bafta",
        ]
        if any(re.search(p, text_lower) for p in top_win_patterns):
            a_bonus = 0.10
        elif any(re.search(p, text_lower) for p in nomination_patterns):
            a_bonus = 0.05

    # 5. Low Context Penalty (P_context)
    # 0.15 if low_context = True, else 0.00
    p_context = 0.15 if low_context else 0.00

    # Parameter Weights (strictly fixed as defined in the image)
    w_v = 0.50
    w_b = 0.25
    w_r = 0.15
    w_a = 0.10

    inner_val = (w_v * v_norm) + (w_r * r_norm) + (w_b * b_norm) + (w_a * a_bonus) - p_context
    d_base = 1.0 - min(1.0, inner_val)

    return {
        "d_base": round(d_base, 3),
        "v_norm": round(v_norm, 3),
        "b_norm": round(b_norm, 3),
        "r_norm": round(r_norm, 3),
        "a_bonus": round(a_bonus, 2),
    }


async def sample_test_batch(sample_size_per_tier: int = 5):
    """
    Selects a stratified sample of 20 movies across 4 categories:
    1. Mega Blockbusters (High votes, high box office)
    2. Acclaimed Classics (Older release year, high rating/awards)
    3. Mid-tier Popular Movies (Moderate vote counts)
    4. Obscure / Indie Movies (Low vote counts)
    """
    async with AsyncSessionLocal() as session:
        # Tier 1: Blockbusters
        q_blockbusters = select(Movie).order_by(desc(Movie.imdb_votes)).limit(sample_size_per_tier)
        res_b = await session.execute(q_blockbusters)
        blockbusters = res_b.scalars().all()

        # Tier 2: Pre-1990 Classics with high ratings
        q_classics = (
            select(Movie)
            .where(Movie.year < 1990, Movie.imdb_rating >= 8.0)
            .order_by(desc(Movie.imdb_rating))
            .limit(sample_size_per_tier)
        )
        res_c = await session.execute(q_classics)
        classics = res_c.scalars().all()

        # Tier 3: Mid-tier (between 30k and 150k votes)
        q_mid = (
            select(Movie)
            .where(Movie.imdb_votes.between(30000, 150000))
            .order_by(Movie.imdb_votes)
            .limit(sample_size_per_tier)
        )
        res_m = await session.execute(q_mid)
        mid_tier = res_m.scalars().all()

        # Tier 4: Obscure (lowest votes in database)
        q_obscure = (
            select(Movie)
            .where(Movie.imdb_votes > 0)
            .order_by(asc(Movie.imdb_votes))
            .limit(sample_size_per_tier)
        )
        res_o = await session.execute(q_obscure)
        obscure = res_o.scalars().all()

        sampled_groups = [
            ("MEGA BLOCKBUSTERS", blockbusters),
            ("ACCLAIMED CLASSICS", classics),
            ("MID-TIER MOVIES", mid_tier),
            ("OBSCURE / INDIE MOVIES", obscure),
        ]

        print("=" * 115)
        print(f"{'TITLE (YEAR)':<32} | {'VOTES':<9} | {'RATING':<6} | {'BOX OFF':<9} | {'AWD':<4} | {'OLD D':<6} | {'NEW D':<6} | {'DELTA':<7}")
        print("=" * 115)

        for group_name, group_movies in sampled_groups:
            print(f"\n--- {group_name} ---")
            for m in group_movies:
                metrics = calculate_exact_image_formula(
                    imdb_votes=m.imdb_votes,
                    imdb_rating=m.imdb_rating,
                    budget=m.budget,
                    revenue=m.revenue,
                    awards_summary=m.awards_summary,
                )
                new_d = metrics["d_base"]
                old_d = round(m.base_difficulty, 3)
                delta = round(new_d - old_d, 3)
                delta_str = f"+{delta}" if delta > 0 else f"{delta}"

                title_year = f"{m.title[:25]} ({m.year})"
                votes_str = f"{m.imdb_votes:,}" if m.imdb_votes else "0"
                rev = max(m.revenue or 0, m.budget or 0)
                rev_str = f"${rev/1e6:.0f}M" if rev >= 1e6 else ("$0" if rev == 0 else f"${rev/1e3:.0f}K")
                awd_str = "Yes" if metrics["a_bonus"] > 0 else "-"

                print(f"{title_year:<32} | {votes_str:<9} | {m.imdb_rating or 0.0:<6.1f} | {rev_str:<9} | {awd_str:<4} | {old_d:<6.3f} | {new_d:<6.3f} | {delta_str:<7}")

        print("\n" + "=" * 115)
        print("READ-ONLY TEST COMPLETE: No changes were written to PostgreSQL.")
        print("=" * 115)


async def apply_to_all_movies(batch_size: int = 500):
    """
    Applies the new difficulty calculation to all movies in batches.
    """
    print(f"\n[APPLY MODE] Updating all movies in database in batches of {batch_size}...")
    async with AsyncSessionLocal() as session:
        total_movies = await session.scalar(select(func.count()).select_from(Movie))
        print(f"Total movies to process: {total_movies}")

        offset = 0
        updated = 0
        while True:
            res = await session.execute(
                select(Movie).order_by(Movie.imdb_id).offset(offset).limit(batch_size)
            )
            batch = res.scalars().all()
            if not batch:
                break

            for m in batch:
                metrics = calculate_exact_image_formula(
                    imdb_votes=m.imdb_votes,
                    imdb_rating=m.imdb_rating,
                    budget=m.budget,
                    revenue=m.revenue,
                    awards_summary=m.awards_summary,
                )
                m.base_difficulty = metrics["d_base"]
                updated += 1

            await session.commit()
            print(f"  Processed {min(offset + batch_size, total_movies)} / {total_movies} movies...")
            offset += batch_size

        print(f"\n Successfully updated base_difficulty for all {updated} movies!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test or Apply Movie Difficulty Engine")
    parser.add_argument("--apply", action="store_true", help="Apply calculation to entire movies table")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if args.apply:
        if args.yes:
            asyncio.run(apply_to_all_movies())
        else:
            confirm = input("Are you sure you want to update all movies in PostgreSQL? (yes/no): ")
            if confirm.strip().lower() == "yes":
                asyncio.run(apply_to_all_movies())
            else:
                print("Operation aborted. Database remains untouched.")
    else:
        asyncio.run(sample_test_batch())
