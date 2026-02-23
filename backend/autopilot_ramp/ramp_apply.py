from decimal import Decimal

from database.database import Database


async def get_current_step_traffic_fraction(experiment_id: str) -> float | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT rs.traffic_fraction
               FROM experiment_ramp_state ers
               JOIN ramp_steps rs ON rs.ramp_plan_id = ers.ramp_plan_id AND rs.step_index = ers.current_step_index
               WHERE ers.experiment_id = $1""",
            (experiment_id,),
        )
        if not row:
            return None
        return float(row["traffic_fraction"])


async def apply_ramp_step_to_experiment(experiment_id: str) -> bool:
    async with Database() as db:
        state = await db.execute(
            """SELECT ers.ramp_plan_id, ers.current_step_index
               FROM experiment_ramp_state ers
               WHERE ers.experiment_id = $1""",
            (experiment_id,))
        if not state:
            return False

        step = await db.execute(
            """SELECT traffic_fraction FROM ramp_steps
               WHERE ramp_plan_id = $1 AND step_index = $2""",
            (state["ramp_plan_id"], state["current_step_index"]))
        if not step:
            return False

        new_af = float(step["traffic_fraction"])

        ex = await db.execute(
            "SELECT id, audience_fraction FROM experiments WHERE id = $1",
            (experiment_id,))
        if not ex:
            return False

        old_af = float(ex["audience_fraction"])
        if old_af <= 0:
            return False

        variants = await db.execute_all(
            "SELECT id, weight FROM experiment_variants WHERE experiment_id = $1 ORDER BY id",
            (experiment_id,))
        if not variants:
            return False

        scale = new_af / old_af
        new_weights = []
        for row in variants:
            w = float(row["weight"])
            new_w = round((w * scale), 4)
            new_weights.append((str(row["id"]), new_w))
        total = sum(nw for _, nw in new_weights)
        if total != new_af and new_weights:
            diff = round(new_af - total, 4)
            vid0, w0 = new_weights[0]
            new_weights[0] = (vid0, max(0, round(w0 + diff, 4)))

        await db.execute("SET LOCAL app.allow_ramp_apply = '1'")

        for vid, nw in new_weights:
            await db.execute(
                "UPDATE experiment_variants SET weight = $1 WHERE id = $2 AND experiment_id = $3",
                (Decimal(str(nw)), vid, experiment_id))
        await db.execute(
            "UPDATE experiments SET audience_fraction = $1, updated_at = NOW() WHERE id = $2",
            (Decimal(str(new_af)), experiment_id))

        return True
