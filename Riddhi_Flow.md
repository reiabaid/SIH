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



for cnet.py

             YOUR MATCHING SYSTEM
                    │
                    ↓
             MatchResult
                    │
          ┌─────────┴─────────┐
          ↓                   ↓
       metrics             cnet.py
          ↓                   ↓
       evaluate          ISIS CNET
                              ↓
                    ISRO photogrammetry

in short:-
"Phase 7 converts the reliable matched points from our MatchResult into an ISIS Control Network file, so that the output of our lunar image matcher can be directly integrated into the existing photogrammetry workflow without needing to install or run ISIS ourselves."

