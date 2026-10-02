import { useEffect, useState } from 'react'
import { currencyApi, placesApi, tripsApi, weatherApi } from '../api/client'
import './TripUtilities.css'

function utilityError(error, fallback, tripScoped = false) {
  if (error.status === 401) return 'Your session has expired. Sign in again to continue.'
  if (error.status === 404 && tripScoped) return 'This trip is unavailable or you do not have access to it.'
  if (error.status === 422) return 'Check the entered location, amount, and currency codes, then try again.'
  if (error.status >= 500) return fallback
  if (!error.status) return 'Could not connect to PACK & GO. Check your connection and retry.'
  return fallback
}

export default function TripUtilities({ trip }) {
  const [packing, setPacking] = useState(null)
  const [map, setMap] = useState(null)
  const [places, setPlaces] = useState(null)
  const [category, setCategory] = useState('attractions')
  const [packingLoading, setPackingLoading] = useState(true)
  const [mapLoading, setMapLoading] = useState(true)
  const [placesLoading, setPlacesLoading] = useState(false)
  const [packingError, setPackingError] = useState('')
  const [mapError, setMapError] = useState('')
  const [placesError, setPlacesError] = useState('')
  const [weatherError, setWeatherError] = useState('')
  const [currencyError, setCurrencyError] = useState('')
  const [currencyLoading, setCurrencyLoading] = useState(false)
  const [routeLocations, setRouteLocations] = useState([])
  const [routeStart, setRouteStart] = useState('')
  const [routeGoal, setRouteGoal] = useState('')
  const [routeResult, setRouteResult] = useState(null)
  const [routeLocationsLoading, setRouteLocationsLoading] = useState(true)
  const [routeLoading, setRouteLoading] = useState(false)
  const [routeError, setRouteError] = useState('')
  const [routeRetryOptimize, setRouteRetryOptimize] = useState(false)
  const [cspResult, setCspResult] = useState(null)
  const [cspLoading, setCspLoading] = useState(false)
  const [cspError, setCspError] = useState('')
  const [gaResult, setGaResult] = useState(null)
  const [gaLoading, setGaLoading] = useState(false)
  const [gaError, setGaError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [currency, setCurrency] = useState({ amount: '', from: trip.budget_currency, to: 'USD' })
  const [conversion, setConversion] = useState(null)
  const [weatherLocation, setWeatherLocation] = useState(trip.destination)
  const [currentWeather, setCurrentWeather] = useState(null)
  const [weatherLoading, setWeatherLoading] = useState(false)

  useEffect(() => {
    let active = true
    setPackingLoading(true)
    setMapLoading(true)
    setPackingError('')
    setMapError('')
    setRouteLocationsLoading(true)
    setRouteError('')
    setRouteResult(null)
    tripsApi.packing(trip.id)
      .then(result => { if (active) setPacking(result) })
      .catch(error => { if (active) setPackingError(utilityError(error, 'Preparation details are temporarily unavailable. Try again.', true)) })
      .finally(() => { if (active) setPackingLoading(false) })
    tripsApi.map(trip.id)
      .then(result => { if (active) setMap(result) })
      .catch(error => { if (active) setMapError(utilityError(error, 'Map locations are temporarily unavailable. Try again.', true)) })
      .finally(() => { if (active) setMapLoading(false) })
    tripsApi.routeLocations(trip.id)
      .then(result => {
        if (!active) return
        setRouteLocations(result.locations || [])
        setRouteStart(current => result.locations?.some(location => location.id === current) ? current : result.locations?.[0]?.id || '')
        setRouteGoal(current => result.locations?.some(location => location.id === current) ? current : result.locations?.at(-1)?.id || '')
      })
      .catch(error => {
        if (active) setRouteError(utilityError(error, 'Route locations are temporarily unavailable. Try again.', true))
      })
      .finally(() => { if (active) setRouteLocationsLoading(false) })
    return () => { active = false }
  }, [trip.id, reloadKey])

  const optimizeRoute = async () => {
    setRouteLoading(true)
    setRouteError('')
    setRouteResult(null)
    setRouteRetryOptimize(true)
    try {
      const result = await tripsApi.optimizeRoute(trip.id, {
        start_location_id: routeStart,
        goal_location_id: routeGoal,
      })
      setRouteResult(result)
      setRouteRetryOptimize(false)
    } catch (error) {
      setRouteError(utilityError(error, 'A* route optimization is temporarily unavailable. Try again.', true))
    } finally {
      setRouteLoading(false)
    }
  }

  const optimizeSchedule = async () => {
    setCspLoading(true)
    setCspError('')
    setCspResult(null)
    try {
      setCspResult(await tripsApi.optimizeItineraryCsp(trip.id))
    } catch (error) {
      setCspError(error.status === 401
        ? 'Your session has expired. Sign in again to continue.'
        : error.status === 404
          ? 'This trip is unavailable or you do not have access to it.'
          : 'The itinerary scheduler is temporarily unavailable. Try again.')
    } finally {
      setCspLoading(false)
    }
  }

  const optimizeGenetic = async () => {
    setGaLoading(true)
    setGaError('')
    setGaResult(null)
    try {
      setGaResult(await tripsApi.optimizeItineraryGa(trip.id))
    } catch (error) {
      setGaError(error.status === 401
        ? 'Your session has expired. Sign in again to continue.'
        : error.status === 404
          ? 'This trip is unavailable or you do not have access to it.'
          : error.status === 422
            ? 'The optimization settings were rejected. Use the supported population and generation limits.'
            : 'Genetic Algorithm optimization is temporarily unavailable. Try again.')
    } finally {
      setGaLoading(false)
    }
  }

  const searchPlaces = async () => {
    setPlacesLoading(true)
    setPlacesError('')
    setPlaces(null)
    try {
      setPlaces(await placesApi.search(trip.destination, category))
    } catch (error) {
      setPlacesError(utilityError(error, 'Place search is temporarily unavailable. Try again shortly.'))
    } finally {
      setPlacesLoading(false)
    }
  }
  const convert = async event => {
    event.preventDefault()
    setCurrencyLoading(true)
    setCurrencyError('')
    setConversion(null)
    try {
      setConversion(await currencyApi.convert(Number(currency.amount), currency.from, currency.to))
    } catch (error) {
      setCurrencyError(utilityError(error, 'Currency conversion is temporarily unavailable. Verify the currencies and retry.'))
    } finally {
      setCurrencyLoading(false)
    }
  }
  const loadCurrentWeather = async event => {
    event.preventDefault()
    setWeatherLoading(true)
    setWeatherError('')
    setCurrentWeather(null)
    try {
      setCurrentWeather(await weatherApi.current(weatherLocation.trim()))
    } catch (error) {
      setWeatherError(utilityError(error, 'Current weather is temporarily unavailable. Try again shortly.'))
    } finally {
      setWeatherLoading(false)
    }
  }

  return <div className="utility-grid">
    <section className="utility-panel">
      <p className="eyebrow">Genetic Algorithm</p><h2>AI Itinerary Optimization</h2>
      <p className="utility-note">Genetic Algorithm evaluates a population of candidate itineraries and iteratively improves them using selection, crossover and mutation.</p>
      <p className="ga-pipeline" aria-label="Population, then selection, crossover, mutation, and a new generation">Population <span aria-hidden="true">→</span> Selection <span aria-hidden="true">→</span> Crossover <span aria-hidden="true">→</span> Mutation <span aria-hidden="true">→</span> New Generation</p>
      <button className="button button-primary" onClick={optimizeGenetic} disabled={gaLoading}>
        {gaLoading ? 'Optimizing itinerary...' : 'Optimize with Genetic Algorithm'}
      </button>
      {gaLoading && <p className="page-lede" role="status">Evolving candidate schedules against saved activity timings and trip days...</p>}
      {gaError && <div><p className="form-error" role="alert">{gaError}</p><button className="button button-quiet" onClick={optimizeGenetic} disabled={gaLoading}>Retry</button></div>}
      {gaResult?.status === 'insufficient_data' && <div>
        <p className="page-lede" role="status">Insufficient itinerary data: {gaResult.message}</p>
        <button className="button button-quiet" onClick={optimizeGenetic} disabled={gaLoading}>Retry</button>
      </div>}
      {gaResult?.status === 'optimized' && <div className="ga-result">
        <p role="status">Preview only. The saved itinerary has not been changed.</p>
        <p><strong>Algorithm:</strong> {gaResult.algorithm}</p>
        <p><strong>Baseline fitness:</strong> {Number(gaResult.baseline_fitness).toFixed(2)} <span>·</span> <strong>Final fitness:</strong> {Number(gaResult.final_fitness).toFixed(2)}</p>
        <p><strong>Generations:</strong> {gaResult.generations_executed} <span>·</span> <strong>Population:</strong> {gaResult.population_size}</p>
        <p className="utility-note">{gaResult.message}</p>
        <div className="ga-days">{gaResult.optimized_itinerary.map(day => <section className="ga-day" key={day.day_number}>
          <h3>Day {day.day_number}</h3>
          <ul>
            {(day.activities || []).map((activity, index) => <li key={`activity-${index}`}>{activity}</li>)}
            {(day.attractions || []).map((attraction, index) => <li key={`attraction-${index}`}>
              {attraction.place?.name || 'Attraction'}{attraction.timing ? <span>{attraction.timing}</span> : null}
            </li>)}
          </ul>
        </section>)}</div>
        <h3>Optimization criteria</h3><ul>{gaResult.applied_criteria.map(item => <li key={item}>{item}</li>)}</ul>
        {gaResult.unavailable_constraints.length > 0 && <>
          <h3>Unavailable constraint data</h3><ul>{gaResult.unavailable_constraints.map(item => <li key={item}>{item}</li>)}</ul>
        </>}
      </div>}
    </section>
    <section className="utility-panel">
      <p className="eyebrow">Constraint Satisfaction Problem</p><h2>AI Itinerary Constraint Optimizer</h2>
      <p className="utility-note">CSP models itinerary planning as variables, domains and constraints. Backtracking searches for a schedule that satisfies the available constraints.</p>
      <button className="button button-primary" onClick={optimizeSchedule} disabled={cspLoading}>
        {cspLoading ? 'Checking schedule...' : 'Check & Optimize Schedule'}
      </button>
      {cspLoading && <p className="page-lede" role="status">Checking saved activities and attraction timings against trip days...</p>}
      {cspError && <div><p className="form-error" role="alert">{cspError}</p><button className="button button-quiet" onClick={optimizeSchedule} disabled={cspLoading}>Retry</button></div>}
      {cspResult?.status === 'valid' && <div className="csp-result">
        <h3 role="status">Valid schedule</h3>
        <p><strong>Algorithm:</strong> {cspResult.algorithm}</p>
        <ul>{cspResult.assignments.map(item => <li key={item.id}>{item.name} <span>Day {item.day_number}{item.timing ? ` · ${item.timing}` : ''}</span></li>)}</ul>
        <h3>Applied constraints</h3><ul>{cspResult.applied_constraints.map(item => <li key={item}>{item}</li>)}</ul>
        <h3>Unavailable constraints</h3><ul>{cspResult.unavailable_constraints.map(item => <li key={item}>{item}</li>)}</ul>
      </div>}
      {cspResult?.status === 'conflicts' && <div className="csp-result">
        <h3 role="status">Conflicts found</h3><p>{cspResult.message}</p>
        <p><strong>Algorithm:</strong> {cspResult.algorithm}</p>
        <ul>{cspResult.conflicts.map((item, index) => <li key={`${item.activities.join('-')}-${index}`}>{item.activities.join(' and ')}: {item.reason} ({item.timing.join(' / ')})</li>)}</ul>
        <h3>Applied constraints</h3><ul>{cspResult.applied_constraints.map(item => <li key={item}>{item}</li>)}</ul>
        <h3>Unavailable constraints</h3><ul>{cspResult.unavailable_constraints.map(item => <li key={item}>{item}</li>)}</ul>
        <button className="button button-quiet" onClick={optimizeSchedule} disabled={cspLoading}>Retry</button>
      </div>}
      {cspResult?.status === 'insufficient_data' && <div>
        <p className="page-lede" role="status">Insufficient itinerary data: {cspResult.message}</p>
        <button className="button button-quiet" onClick={optimizeSchedule} disabled={cspLoading}>Retry</button>
      </div>}
    </section>
    <section className="utility-panel">
      <p className="eyebrow">A* Search</p><h2>AI Route Optimization</h2>
      <p className="utility-note">A* combines distance traveled so far, g(n), with estimated straight-line distance to the goal, h(n), to find a shortest path between selected itinerary stops. It does not globally reorder every stop.</p>
      {routeLocationsLoading ? <p className="page-lede" role="status">Loading itinerary coordinates...</p> : routeError ? <div><p className="form-error" role="alert">{routeError}</p><button className="button button-quiet" onClick={() => routeRetryOptimize ? optimizeRoute() : setReloadKey(value => value + 1)}>Retry</button></div> : routeLocations.length < 2 ? <p className="page-lede">Route optimization needs at least two itinerary attractions with saved latitude and longitude. No coordinates are inferred.</p> : <>
        <div className="utility-controls route-controls">
          <label>Start location<select value={routeStart} onChange={event => setRouteStart(event.target.value)}>{routeLocations.map(location => <option key={location.id} value={location.id}>{location.name}</option>)}</select></label>
          <label>Destination<select value={routeGoal} onChange={event => setRouteGoal(event.target.value)}>{routeLocations.map(location => <option key={location.id} value={location.id}>{location.name}</option>)}</select></label>
          <button className="button button-primary" onClick={optimizeRoute} disabled={routeLoading || !routeStart || !routeGoal || routeStart === routeGoal}>{routeLoading ? 'Optimizing...' : 'Optimize Route'}</button>
        </div>
        {routeLoading && <p className="page-lede" role="status">Searching the itinerary location graph...</p>}
        {routeResult?.status === 'optimized' && <div className="route-result"><h3>Optimized Route</h3><ol>{routeResult.route.ordered_locations.map(location => <li key={location.id}>{location.name}</li>)}</ol><p><strong>Algorithm:</strong> A* Search</p><p><strong>Total Distance:</strong> {Number(routeResult.route.total_distance_km).toFixed(1)} km <span className="utility-note">(straight-line graph estimate)</span></p></div>}
        {routeResult && routeResult.status !== 'optimized' && <div><p className="page-lede" role="status">{routeResult.message}</p>{routeResult.status === 'unreachable' && <button className="button button-quiet" onClick={optimizeRoute} disabled={routeLoading}>Retry</button>}</div>}
      </>}
    </section>
    <section className="utility-panel">
      <p className="eyebrow">Travel preparation</p><h2>Packing list</h2>
      {packingLoading ? <p className="page-lede" role="status">Loading preparation details...</p> : packingError ? <div><p className="form-error" role="alert">{packingError}</p><button className="button button-quiet" onClick={() => setReloadKey(value => value + 1)}>Retry</button></div> : packing?.items?.length ? <>
        {Object.entries(packing.categories || {}).map(([name, items]) => items.length > 0 && <div className="utility-category" key={name}><h3>{name}</h3><ul>{items.map(item => <li key={item}>{item}</li>)}</ul></div>)}
        <h3>Before you go</h3><ul>{(packing.preparation || []).map(item => <li key={item}>{item}</li>)}</ul>
      </> : <p className="page-lede">No preparation items are available for this trip.</p>}
    </section>
    <section className="utility-panel">
      <p className="eyebrow">Trip map</p><h2>Places in your itinerary</h2>
      {mapLoading ? <p className="page-lede" role="status">Loading map locations...</p> : mapError ? <div><p className="form-error" role="alert">{mapError}</p><button className="button button-quiet" onClick={() => setReloadKey(value => value + 1)}>Retry</button></div> : map?.locations?.length ? <ul>{map.locations.map(location => <li key={`${location.type}-${location.name}`}><a href={location.search_url} target="_blank" rel="noreferrer">{location.name}</a><span>{location.type}</span></li>)}</ul> : <p className="page-lede">No itinerary locations are available.</p>}
      <p className="utility-note">Locations open as OpenStreetMap search results.</p>
    </section>
    <section className="utility-panel">
      <p className="eyebrow">Live lookup</p><h2>Places near {trip.destination}</h2>
      <div className="utility-controls"><select value={category} onChange={event => setCategory(event.target.value)} aria-label="Place category"><option value="attractions">Attractions</option><option value="restaurants">Restaurants</option><option value="activities">Activities</option><option value="transportation">Transportation</option><option disabled>Hotels (not supported)</option><option disabled>Emergency locations (not supported)</option></select><button className="button button-primary" onClick={searchPlaces} disabled={placesLoading}>{placesLoading ? 'Searching...' : 'Search'}</button></div>
      <p className="utility-note">Hotel and emergency search are not supported by the current places provider.</p>
      {placesError && <p className="form-error" role="alert">{placesError}</p>}
      {placesLoading && <p className="page-lede" role="status">Searching places...</p>}
      {!placesLoading && places && (places.results ? <pre className="utility-results">{typeof places.results === 'string' ? places.results : JSON.stringify(places.results, null, 2)}</pre> : <p className="page-lede">No results were returned for this category.</p>)}
        {!placesLoading && !places && !placesError && <p className="page-lede">Search to see live results for this category.</p>}
      {placesError && <button className="button button-quiet" onClick={searchPlaces}>Retry search</button>}
    </section>
    <section className="utility-panel">
      <p className="eyebrow">Exchange rates</p><h2>Convert currency</h2>
      <form className="utility-controls currency-form" onSubmit={convert}><input type="number" min="0.01" step="0.01" value={currency.amount} onChange={event => setCurrency({ ...currency, amount: event.target.value })} placeholder="Amount" aria-label="Amount" required /><input value={currency.from} onChange={event => setCurrency({ ...currency, from: event.target.value.toUpperCase() })} maxLength="3" aria-label="Source currency" required /><input value={currency.to} onChange={event => setCurrency({ ...currency, to: event.target.value.toUpperCase() })} maxLength="3" aria-label="Target currency" required /><button className="button button-primary" disabled={currencyLoading}>{currencyLoading ? 'Converting...' : 'Convert'}</button></form>
      {currencyError && <p className="form-error" role="alert">{currencyError}</p>}
      {currencyLoading && <p className="page-lede" role="status">Fetching the latest available rate...</p>}
      {conversion && <><p className="utility-result">{conversion.amount} {conversion.from_currency} = <strong>{Number(conversion.converted_amount).toFixed(2)} {conversion.to_currency}</strong></p><p className="utility-note">Source: {conversion.source} · {conversion.status}</p></>}
    </section>
    <section className="utility-panel">
      <p className="eyebrow">Live lookup</p><h2>Current weather</h2>
      <form className="utility-controls" onSubmit={loadCurrentWeather}><input value={weatherLocation} onChange={event => setWeatherLocation(event.target.value)} maxLength="255" aria-label="Weather location" required /><button className="button button-primary" disabled={weatherLoading}>{weatherLoading ? 'Checking...' : 'Check current weather'}</button></form>
      {weatherError && <p className="form-error" role="alert">{weatherError}</p>}
      {weatherLoading && <p className="page-lede" role="status">Loading current weather...</p>}
      {currentWeather && <div className="utility-result"><strong>{currentWeather.conditions}</strong><p>{currentWeather.summary}</p><p>{currentWeather.temperature_range}</p><p className="utility-note">Current conditions · {currentWeather.data_source === 'live_api' ? 'OpenWeather live data' : 'Provider data status unavailable'}</p></div>}
      {!weatherLoading && !weatherError && !currentWeather && <p className="page-lede">Check current conditions for a location.</p>}
    </section>
    <section className="utility-panel">
      <p className="eyebrow">Saved trip data</p><h2>Preparation weather</h2>
      {trip.weather ? <><p className="utility-result"><strong>{trip.weather.conditions || 'Conditions not recorded'}</strong></p><p className="page-lede">{trip.weather.summary || 'No weather summary was saved for this trip.'}</p><p>{trip.weather.temperature_range || 'Temperature unavailable'}</p><p className="utility-note">Used for preparation suggestions. This is saved trip weather, not a live forecast.</p></> : <p className="page-lede">No weather data was saved with this trip. Check current weather above before departure.</p>}
    </section>
  </div>
}