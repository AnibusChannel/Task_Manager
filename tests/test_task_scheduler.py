import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import task_scheduler as ts


class TaskSchedulerTests(unittest.TestCase):
    def _capture_output(self, callback) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            callback()
        return buf.getvalue()

    def test_deadline_task_validation(self) -> None:
        with self.assertRaises(ValueError):
            ts.DeadlineTask(-1, "t", "a", 5, 10, 20)
        with self.assertRaises(ValueError):
            ts.DeadlineTask(1, "t", "a", 11, 10, 20)
        with self.assertRaises(ValueError):
            ts.DeadlineTask(1, "t", "a", 5, 0, 20)
        with self.assertRaises(ValueError):
            ts.DeadlineTask(1, "t", "a", 5, 10, -1)

    def test_change_priority_validation(self) -> None:
        task = ts.OverdueTask(1, "urgent", "bob", 5, 10)
        with self.assertRaises(ValueError):
            task.changePriority(0)
        with self.assertRaises(ValueError):
            task.changePriority(11)
        task.changePriority(8)
        self.assertEqual(task.getPriority(), 8)

    def test_deadline_extension(self) -> None:
        task = ts.DeadlineTask(2, "report", "ann", 4, 15, 100)
        task.extendDeadline(20)
        self.assertEqual(task.getDeadline(), 120)
        with self.assertRaises(ValueError):
            task.extendDeadline(-1)

    def test_periodic_task_validation_and_skip(self) -> None:
        with self.assertRaises(ValueError):
            ts.PeriodicTask(1, "sync", "ann", 3, 5, -1, 10)
        with self.assertRaises(ValueError):
            ts.PeriodicTask(1, "sync", "ann", 3, 5, 0, 0)

        task = ts.PeriodicTask(1, "sync", "ann", 3, 5, 10, 7)
        self.assertEqual(task.getNextExecutionTime(), 10)
        task.skipNextExecution()
        self.assertEqual(task.getNextExecutionTime(), 17)
        self.assertEqual(task.getPeriod(), 7)

    def test_overdue_can_execute(self) -> None:
        task = ts.OverdueTask(3, "urgent", "tom", 7, 5)
        self.assertTrue(task.canExecute(7))
        self.assertTrue(task.canExecute(5))
        self.assertFalse(task.canExecute(8))
        self.assertEqual(task.getNextExecutionTime(), 0)

    def test_plan_add_remove_and_getters(self) -> None:
        plan = ts.Plan()
        with self.assertRaises(ValueError):
            plan.addTask(None)  # type: ignore[arg-type]

        t1 = ts.DeadlineTask(1, "a", "alice", 5, 5, 30)
        t2 = ts.OverdueTask(2, "b", "bob", 7, 3)
        plan.addTask(t1)
        plan.addTask(t2)

        self.assertEqual(plan.getTaskCount(), 2)
        self.assertIs(plan.getTask(1), t1)
        self.assertIsNone(plan.getTask(42))
        self.assertEqual(plan.getTasksByAssignee("bob"), [t2])
        self.assertEqual(plan.getTasksByAssignee("nobody"), [])
        self.assertTrue(plan.removeTask(2))
        self.assertFalse(plan.removeTask(2))
        self.assertEqual(plan.getTaskCount(), 1)

    def test_plan_get_next_task_uses_min_execution_time(self) -> None:
        plan = ts.Plan()
        t1 = ts.DeadlineTask(1, "late", "a", 1, 1, 50)
        t2 = ts.OverdueTask(2, "urgent", "a", 10, 1)
        t3 = ts.PeriodicTask(3, "period", "a", 4, 1, 20, 5)
        plan.addTask(t1)
        plan.addTask(t2)
        plan.addTask(t3)
        self.assertIs(plan.getNextTask(), t2)

    def test_execute_next_removes_non_periodic_task(self) -> None:
        plan = ts.Plan()
        overdue = ts.OverdueTask(1, "urgent", "bob", 9, 5)
        plan.addTask(overdue)
        plan.executeNextTask()
        self.assertTrue(plan.isEmpty())

    def test_execute_next_reschedules_periodic_task(self) -> None:
        plan = ts.Plan()
        periodic = ts.PeriodicTask(10, "poll", "ops", 4, 5, 8, 3)
        plan.addTask(periodic)
        plan.executeNextTask()
        self.assertEqual(plan.getTaskCount(), 1)
        self.assertEqual(periodic.getNextExecutionTime(), 11)

    def test_scheduler_build_optimal_plan_order(self) -> None:
        scheduler = ts.Scheduler()
        tasks = [
            ts.DeadlineTask(1, "d", "a", 4, 5, 100),
            ts.PeriodicTask(2, "p", "a", 4, 5, 30, 10),
            ts.OverdueTask(3, "o", "a", 9, 3),
        ]
        scheduler.buildOptimalPlan(tasks)
        ordered = scheduler.plan.getAllTasks()
        self.assertEqual([task.getId() for task in ordered], [3, 2, 1])

    def test_scheduler_run_finishes_without_periodic_tasks(self) -> None:
        scheduler = ts.Scheduler()
        scheduler.addOverdueTask(1, "o", "a", 9, 2)
        scheduler.addDeadlineTask(2, "d", "a", 4, 3, 10)
        scheduler.run()
        self.assertTrue(scheduler.plan.isEmpty())

    def test_scheduler_run_with_periodic_stops_by_max_steps(self) -> None:
        scheduler = ts.Scheduler()
        scheduler.addPeriodicTask(1, "p", "a", 5, 2, 0, 3)
        scheduler.run(max_steps=3)
        self.assertEqual(scheduler.plan.getTaskCount(), 1)
        periodic = scheduler.plan.getTask(1)
        self.assertIsInstance(periodic, ts.PeriodicTask)
        self.assertEqual(periodic.getNextExecutionTime(), 9)

    def test_ostream_redirect_redirects_stdout_and_restores(self) -> None:
        buf = io.StringIO()
        original_stdout = ts.sys.stdout
        with ts.ostream_redirect(stdout=True, stderr=False, target=buf):
            print("hello")
        self.assertIn("hello", buf.getvalue())
        self.assertIs(ts.sys.stdout, original_stdout)

    def test_get_all_tasks_returns_copy_not_internal_list(self) -> None:
        plan = ts.Plan()
        task = ts.OverdueTask(1, "x", "a", 2, 1)
        plan.addTask(task)
        all_tasks = plan.getAllTasks()
        all_tasks.clear()
        self.assertEqual(plan.getTaskCount(), 1)

    def test_get_next_task_none_for_empty_plan(self) -> None:
        plan = ts.Plan()
        self.assertIsNone(plan.getNextTask())

    def test_execute_next_task_on_empty_plan_prints_message(self) -> None:
        plan = ts.Plan()
        out = self._capture_output(plan.executeNextTask)
        self.assertIn("No tasks to execute", out)

    def test_display_all_tasks_for_empty_plan(self) -> None:
        plan = ts.Plan()
        out = self._capture_output(plan.displayAllTasks)
        self.assertIn("Plan is empty", out)

    def test_display_info_methods_emit_expected_class_names(self) -> None:
        def _run() -> None:
            ts.DeadlineTask(1, "d", "a", 4, 1, 9).displayInfo()
            ts.PeriodicTask(2, "p", "a", 4, 1, 9, 2).displayInfo()
            ts.OverdueTask(3, "o", "a", 4, 1).displayInfo()

        out = self._capture_output(_run)
        self.assertIn("DeadlineTask(", out)
        self.assertIn("PeriodicTask(", out)
        self.assertIn("OverdueTask(", out)

    def test_scheduler_add_task_none_raises(self) -> None:
        scheduler = ts.Scheduler()
        with self.assertRaises(ValueError):
            scheduler.addTask(None)  # type: ignore[arg-type]

    def test_build_optimal_plan_with_empty_input(self) -> None:
        scheduler = ts.Scheduler()
        out = self._capture_output(lambda: scheduler.buildOptimalPlan([]))
        self.assertEqual(scheduler.plan.getTaskCount(), 0)
        self.assertIn("Tasks added: 0", out)

    def test_scheduler_get_assignee_tasks(self) -> None:
        scheduler = ts.Scheduler()
        scheduler.addOverdueTask(1, "a", "alice", 7, 2)
        scheduler.addDeadlineTask(2, "b", "bob", 5, 3, 9)
        scheduler.addPeriodicTask(3, "c", "alice", 3, 1, 5, 2)
        assignee_tasks = scheduler.getAssigneeTasks("alice")
        self.assertEqual({task.getId() for task in assignee_tasks}, {1, 3})

    def test_scheduler_execute_next_delegates_to_plan(self) -> None:
        scheduler = ts.Scheduler()
        scheduler.addDeadlineTask(10, "d", "a", 5, 2, 5)
        scheduler.executeNext()
        self.assertTrue(scheduler.plan.isEmpty())

    def test_scheduler_display_plan_when_empty(self) -> None:
        scheduler = ts.Scheduler()
        out = self._capture_output(scheduler.displayPlan)
        self.assertIn("=== CURRENT PLAN ===", out)
        self.assertIn("Task count: 0", out)
        self.assertIn("Next task: none", out)

    def test_scheduler_display_plan_when_has_tasks(self) -> None:
        scheduler = ts.Scheduler()
        scheduler.addDeadlineTask(1, "later", "a", 5, 2, 10)
        scheduler.addOverdueTask(2, "now", "a", 9, 2)
        out = self._capture_output(scheduler.displayPlan)
        self.assertIn("Task count: 2", out)
        self.assertIn("Next task: ID=2", out)

    def test_run_empty_plan_completes_immediately(self) -> None:
        scheduler = ts.Scheduler()
        out = self._capture_output(scheduler.run)
        self.assertIn("Scheduler started...", out)
        self.assertIn("All tasks are completed", out)

    def test_run_with_max_steps_stops_and_keeps_periodic(self) -> None:
        scheduler = ts.Scheduler()
        scheduler.addPeriodicTask(1, "p", "a", 5, 2, 1, 4)
        out = self._capture_output(lambda: scheduler.run(max_steps=2))
        self.assertIn("Stopped by step limit (2)", out)
        periodic = scheduler.plan.getTask(1)
        self.assertIsInstance(periodic, ts.PeriodicTask)
        self.assertEqual(periodic.getNextExecutionTime(), 9)

    def test_execute_next_prioritizes_execution_time_not_priority(self) -> None:
        plan = ts.Plan()
        high_priority_late = ts.DeadlineTask(1, "high", "a", 10, 1, 50)
        low_priority_soon = ts.DeadlineTask(2, "low", "a", 1, 1, 10)
        plan.addTask(high_priority_late)
        plan.addTask(low_priority_soon)
        self.assertIs(plan.getNextTask(), low_priority_soon)


if __name__ == "__main__":
    unittest.main()

