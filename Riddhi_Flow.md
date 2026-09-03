complete project flow now for Riddhi's Division

             Product A
                +
             Product B
                │
                ↓
        Phase 1: Geometry
        footprint_overlap()
                │
                ↓
        Do they overlap?
                │
                ↓
        Phase 2: Alignment
          align_pair()
                │
                ↓
       Same scale / same grid
                │
                ↓
            match.py
                │
                ↓
          MatchResult
                │
        ┌───────┴────────┐
        ↓                ↓
 Phase 3             Phase 4
 RMSE +              Coverage +
 Inliers             distribution
        │                │
        └───────┬────────┘
                ↓
          Phase 5
       report.py
          /       \
         ↓         ↓
      PNG         JSON
     visual      metrics



About phase 6
MoonAnything Benchmark Survey



              MoonAnything
                   ↓
             Test image pair
                   ↓
             align_pair()
                   ↓
                match()
                   ↓
             MatchResult
                   ↓
       ┌───────────┴───────────┐
       ↓                       ↓
     RMSE                  Coverage
       ↓                       ↓
       └───────────┬───────────┘
                   ↓
              report.py
                   ↓
              Results