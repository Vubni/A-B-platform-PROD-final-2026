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
            (experiment_id,),
        )
        if not state:
            return False

        step = await db.execute(
            """SELECT traffic_fraction FROM ramp_steps
               WHERE ramp_plan_id = $1 AND step_index = $2""",
            (state["ramp_plan_id"], state["current_step_index"]),
        )
        if not step:
            return False

        _ = float(step["traffic_fraction"])
        return True
