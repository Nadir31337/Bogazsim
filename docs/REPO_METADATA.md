# Repository Metadata & GitHub Configuration

This document specifies the suggested repository settings, short description, topic tags, and the exact GitHub CLI (`gh`) command to apply them to `Nadir31337/Bogazsim`.

---

## 1. Description (< 120 characters)

```text
Bosphorus Strait hydrodynamics, Monte Carlo SAR swarm dispersion, datum backtracking & vessel routing simulator.
```

- **Character Count**: 112 characters (well within GitHub's 350-character limit and optimal for search/display under 120 characters).

---

## 2. Website URL

- **Value**: Blank (or URL of live deployment / GitHub Pages if hosted).

---

## 3. Topics (10 Tags)

- `bosphorus`
- `maritime`
- `simulation`
- `search-and-rescue`
- `monte-carlo`
- `a-star`
- `fastapi`
- `digital-twin`
- `numerical-methods`
- `python`

---

## 4. GitHub CLI Command

To configure the repository description and topic tags in one command using the GitHub CLI (`gh`):

```bash
gh repo edit Nadir31337/Bogazsim \
  --description "Bosphorus Strait hydrodynamics, Monte Carlo SAR swarm dispersion, datum backtracking & vessel routing simulator." \
  --add-topic "bosphorus,maritime,simulation,search-and-rescue,monte-carlo,a-star,fastapi,digital-twin,numerical-methods,python"
```

> [!NOTE]
> If you have not yet authenticated with GitHub CLI, run `gh auth login` first.
