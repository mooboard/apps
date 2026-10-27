# Dune

Four layers of wind-shaped dunes with drifting sand, illuminated crests, shaded slopes, fine furrows, a low sun, and slowly changing warm light. Ridges move at different rates to give the landscape depth. The scene runs locally and needs no clock, location, microphone, or network service.

Sand tone sets the terrain color; very dark colors are lifted to keep the dunes visible. Wind speed selects Slow, Normal, or Fast and changes ridge motion and blowing sand. Both settings apply without restarting the scene. The original `color` and `speed` setting keys and types are preserved, so saved choices carry across from the prototype package.

Uses `dune`, version 1.1.0, minimum firmware 0.3.2. The dedicated renderer is implemented on the local `task/app-lab-20261027` firmware branch and must be integrated before this package is published. Board validation is pending. Each turn starts a seeded desert.
