from src.core import validate_game, combination_count
from src.optimizer import optimize_with_constraint_generation


def main():
    print("Universal Lottery / Combination Optimizer - CLI Demo")
    number_from = int(input("Number From: "))
    number_to = int(input("Number To: "))
    ticket_size = int(input("Ticket Size: "))
    result_size = int(input("Result Size: "))
    validate_game(number_from, number_to, ticket_size, result_size)

    print("Enter exact-match targets. Example: 4:10,5:1")
    raw = input("Targets: ").strip()
    targets = {}
    if raw:
        for part in raw.split(","):
            k, v = part.split(":")
            targets[int(k.strip())] = int(v.strip())

    print("Possible tickets:", combination_count(number_from, number_to, ticket_size))
    print("Possible results:", combination_count(number_from, number_to, result_size))

    result = optimize_with_constraint_generation(
        number_from,
        number_to,
        ticket_size,
        result_size,
        targets,
        time_limit_seconds=60,
    )

    print("\nStatus:", result.get("status"))
    print("Rounds:", result.get("rounds"))
    print("Tickets:", result.get("objective"))
    if result.get("tickets"):
        for i, t in enumerate(result["tickets"], 1):
            print(i, t)

    verification = result.get("verification")
    if verification:
        print("\nVerification:")
        print("Total results checked:", verification["total_results_checked"])
        for k, st in sorted(verification["stats"].items()):
            print(f"Exact {k}: min={st['min']} max={st['max']} avg={st['avg']:.3f}")
        print("Targets pass:", verification["all_targets_pass"])


if __name__ == "__main__":
    main()
