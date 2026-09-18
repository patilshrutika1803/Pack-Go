import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { checklistApi, decisionsApi, groupTripsApi, invitationsApi, membersApi, messagesApi, notificationsApi, proposalsApi, tripsApi } from '../api/client'
import { useAuth } from '../auth/useAuth'
import PlanCard from '../components/PlanCard'
import { GroupChat } from '../components/group/GroupChat'
import { GroupChecklist } from '../components/group/GroupChecklist'
import { GroupDecisions } from '../components/group/GroupDecisions'
import { GroupInvitations } from '../components/group/GroupInvitations'
import { GroupMembers } from '../components/group/GroupMembers'
import { GroupNotifications } from '../components/group/GroupNotifications'
import { GroupOverview } from '../components/group/GroupOverview'
import { GroupProposals } from '../components/group/GroupProposals'

function tripToPlan(trip) {
  return {
    trip_id: trip.id,
    preferences: {
      destination: trip.destination,
      duration: trip.duration,
      total_budget: trip.total_budget,
      budget_currency: trip.budget_currency,
      group_size: trip.group_size,
      travelers: trip.group_size,
      travel_style: trip.travel_style,
      travel_dates: trip.travel_dates,
      interests: trip.interests,
    },
    itinerary: trip.itinerary,
    weather: trip.weather,
    budget: trip.budget_breakdown,
    critic_review: trip.critic_review,
  }
}

export default function TripDetailPage() {
  const { tripId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [trip, setTrip] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [workspace, setWorkspace] = useState(null)
  const [tab, setTab] = useState(() => new URLSearchParams(location.search).get('tab') || 'overview')
  const [proposals, setProposals] = useState([])
  const [checklist, setChecklist] = useState([])
  const [inviteEmail, setInviteEmail] = useState('')
    const [messages, setMessages] = useState([]) 
  const [messageCursor, setMessageCursor] = useState(null)
  const [checklistFilter, setChecklistFilter] = useState('all')
  const [checklistDescription, setChecklistDescription] = useState('')
  const [checklistAssignee, setChecklistAssignee] = useState('')
  const [checklistDueAt, setChecklistDueAt] = useState('')
  const [draft, setDraft] = useState('')
  const [notifications, setNotifications] = useState([])
  const [invitations, setInvitations] = useState([])
  const [decisions, setDecisions] = useState([])
  const [proposalResults, setProposalResults] = useState({})
  const [sectionLoading, setSectionLoading] = useState(false)
  const refreshGeneration = useRef(0)
  useEffect(() => {
    tripsApi.get(tripId).then(setTrip).then(() => groupTripsApi.workspace(tripId).then(setWorkspace).catch(() => {})).catch(err => setError(err.message)).finally(() => setLoading(false))
  }, [tripId])
  useEffect(() => {
    if (!workspace) return
    const generation = ++refreshGeneration.current
    const isCurrent = () => generation === refreshGeneration.current
    const load = async () => {
      setSectionLoading(true)
      try {
        if (tab === 'proposals') {
          const result = await proposalsApi.list(tripId)
          const entries = await Promise.all(result.proposals.map(async proposal => [proposal.id, await proposalsApi.results(proposal.id)]))
          if (isCurrent()) { setProposals(result.proposals); setProposalResults(Object.fromEntries(entries)) }
        }
        if (tab === 'checklist') {
          const filters = checklistFilter === 'all' ? {} : checklistFilter === 'overdue' ? { overdue: true } : { completed: checklistFilter === 'completed' }
          const result = await checklistApi.list(tripId, filters)
          if (isCurrent()) setChecklist(result)
        }
        if (tab === 'chat') {
          const result = await messagesApi.list(tripId)
          if (isCurrent()) { setMessages(result.messages); setMessageCursor(result.next_cursor) }
        }
        if (tab === 'notifications') {
          const result = await notificationsApi.list()
          if (isCurrent()) setNotifications(result.notifications)
        }
        if (tab === 'members') {
          const result = await invitationsApi.list(tripId)
          if (isCurrent()) setInvitations(result)
        }
        if (tab === 'decisions') {
          const result = await decisionsApi.list(tripId)
          if (isCurrent()) setDecisions(result)
        }
      } catch (err) {
        if (isCurrent()) setError(err.message)
      } finally {
        if (isCurrent()) setSectionLoading(false)
      }
    }
    load()
    return () => { refreshGeneration.current += 1 }
  }, [tab, tripId, workspace, checklistFilter])
  useEffect(() => {
    if (!workspace) return undefined
    let active = true
    let requestInFlight = false
    const refresh = window.setInterval(async () => {
      if (!active || requestInFlight) return
      requestInFlight = true
      const generation = ++refreshGeneration.current
      try {
        if (tab === 'proposals') {
          const result = await proposalsApi.list(tripId)
          if (active && generation === refreshGeneration.current) setProposals(result.proposals)
        }
        if (tab === 'checklist') {
          const filters = checklistFilter === 'all' ? {} : checklistFilter === 'overdue' ? { overdue: true } : { completed: checklistFilter === 'completed' }
          const result = await checklistApi.list(tripId, filters)
          if (active && generation === refreshGeneration.current) setChecklist(result)
        }
        if (tab === 'chat') {
          const result = await messagesApi.list(tripId)
          if (active && generation === refreshGeneration.current) { setMessages(result.messages); setMessageCursor(result.next_cursor) }
        }
        if (tab === 'notifications') {
          const result = await notificationsApi.list()
          if (active && generation === refreshGeneration.current) setNotifications(result.notifications)
        }
      } catch (err) {
        if (active && generation === refreshGeneration.current) setError(err.message)
      } finally {
        requestInFlight = false
      }
    }, 20000)
    return () => { active = false; refreshGeneration.current += 1; window.clearInterval(refresh) }
  }, [tab, tripId, workspace, checklistFilter])
  const remove = async () => {
    if (!window.confirm('Delete this trip permanently?')) return
    try { await tripsApi.remove(tripId); navigate('/trips', { replace: true, state: { message: 'Trip deleted successfully.' } }) } catch (err) { setError(err.message) }
  }
  const regenerate = async (dayNumber) => {
    setMessage('Regenerating day...'); setError('')
    try {
      const result = await tripsApi.regenerateDay(tripId, dayNumber)
      setTrip(current => ({ ...current, itinerary: current.itinerary.map(day => day.day_number === dayNumber ? result.regenerated_day : day), updated_at: result.updated_at }))
      setMessage(`Day ${dayNumber} regenerated successfully.`)
    } catch (err) { setError(err.message); setMessage('') }
  }
  const convert = async () => { try { setWorkspace(await groupTripsApi.convert(tripId)) } catch (err) { setError(err.message) } }
  const createProposal = async payload => { try { await proposalsApi.create(tripId, payload); setTab('proposals') } catch (err) { setError(err.message) } }
  const mutateProposal = async (action, id, payload) => { try { await action(id, payload); const result = await proposalsApi.list(tripId); setProposals(result.proposals) } catch (err) { setError(err.message) } }
  const refreshChecklist = async () => setChecklist(await checklistApi.list(tripId, checklistFilter === 'all' ? {} : checklistFilter === 'overdue' ? { overdue: true } : checklistFilter === 'open' ? { completed: false } : { completed: true }))
  const refreshMessages = async () => { const result = await messagesApi.list(tripId); setMessages(result.messages); setMessageCursor(result.next_cursor) }
  const refreshNotifications = async () => setNotifications((await notificationsApi.list()).notifications)
  const sendMessage = async () => { if (!draft.trim()) return; try { await messagesApi.create(tripId, draft); setDraft(''); await refreshMessages() } catch (err) { setError(err.message) } }
  const addChecklist = async () => { if (!draft.trim()) return; try { await checklistApi.create(tripId, { title: draft.trim(), description: checklistDescription || undefined, assigned_to_user_id: checklistAssignee || undefined, due_at: checklistDueAt ? new Date(checklistDueAt).toISOString() : undefined }); setDraft(''); setChecklistDescription(''); setChecklistAssignee(''); setChecklistDueAt(''); await refreshChecklist() } catch (err) { setError(err.message) } }
  const updateChecklist = async item => { try { await (item.completed ? checklistApi.reopen(item.id) : checklistApi.complete(item.id)); await refreshChecklist() } catch (err) { setError(err.message) } }
  const editChecklist = async item => { const title = window.prompt('Checklist title', item.title); if (!title?.trim()) return; try { await checklistApi.update(item.id, { title: title.trim() }); await refreshChecklist() } catch (err) { setError(err.message) } }
  const assignChecklist = async (item, assignedToUserId) => { try { await checklistApi.update(item.id, { assigned_to_user_id: assignedToUserId || null }); await refreshChecklist() } catch (err) { setError(err.message) } }
  const deleteChecklist = async id => { try { await checklistApi.remove(id); await refreshChecklist() } catch (err) { setError(err.message) } }
  const invite = async () => { try { const created = await invitationsApi.create(tripId, {}); sessionStorage.setItem(`pack-go-invitation-${created.id}`, created.token); setInvitations(current => [created, ...current]); await navigator.clipboard?.writeText(`${window.location.origin}/invitations/${created.token}`).catch(() => {}); setMessage('Invitation link created and copied.') } catch (err) { setError(err.message) } }
  const updateMember = async (memberId, role) => { try { const updated = await membersApi.updateRole(tripId, memberId, role); setWorkspace(current => ({ ...current, members: current.members.map(member => member.id === updated.id ? { ...member, role: updated.role } : member) })) } catch (err) { setError(err.message) } }
  const removeMember = async memberId => { if (!window.confirm('Remove this member?')) return; try { await membersApi.remove(tripId, memberId); setWorkspace(current => ({ ...current, members: current.members.filter(member => member.user_id !== memberId), member_count: current.member_count - 1 })) } catch (err) { setError(err.message) } }
  const revokeInvitation = async invitationId => { try { await invitationsApi.revoke(invitationId); setInvitations(current => current.map(invitation => invitation.id === invitationId ? { ...invitation, status: 'revoked' } : invitation)) } catch (err) { setError(err.message) } }
  const leave = async () => { if (!window.confirm('Leave this group?')) return; try { await membersApi.leave(tripId); navigate('/trips') } catch (err) { setError(err.message) } }
  const transfer = async targetId => { if (!window.confirm('Transfer ownership? You will become a group admin.')) return; try { setWorkspace(await membersApi.transfer(tripId, targetId).then(() => groupTripsApi.workspace(tripId))) } catch (err) { setError(err.message) } }
  const applyDecision = async decisionId => { try { const updated = await decisionsApi.apply(decisionId); setDecisions(current => current.map(decision => decision.id === updated.id ? updated : decision)); setTrip(await tripsApi.get(tripId)) } catch (err) { setError(err.message) } }
  const replanDecision = async decisionId => { try { const updated = await decisionsApi.replan(decisionId); setDecisions(current => current.map(decision => decision.id === updated.id ? updated : decision)); setTrip(await tripsApi.get(tripId)) } catch (err) { setError(err.message) } }
  const editMessage = async item => { const body = window.prompt('Edit message', item.body); if (!body?.trim()) return; try { await messagesApi.update(item.id, body); await refreshMessages() } catch (err) { setError(err.message) } }
  const deleteMessage = async id => { try { await messagesApi.remove(id); await refreshMessages() } catch (err) { setError(err.message) } }
  const loadOlderMessages = async () => { if (!messageCursor) return; try { const result = await messagesApi.list(tripId, messageCursor); setMessages(current => [...result.messages, ...current]); setMessageCursor(result.next_cursor) } catch (err) { setError(err.message) } }
  const readNotification = async id => { try { await notificationsApi.read(id); await refreshNotifications() } catch (err) { setError(err.message) } }
  const readAllNotifications = async () => { try { await notificationsApi.readAll(); await refreshNotifications() } catch (err) { setError(err.message) } }
  const openNotification = notification => { if (notification.trip_id) setTab(notification.event_type.includes('proposal') || notification.event_type.includes('decision') ? 'proposals' : notification.event_type.includes('checklist') ? 'checklist' : notification.event_type.includes('message') ? 'chat' : 'members') }
  if (loading) return <section className="page-container placeholder"><p className="eyebrow">Trip detail</p><h1>Loading your itinerary...</h1></section>
  if (error || !trip) return <section className="page-container placeholder"><p className="form-error" role="alert">{error || 'Trip not found.'}</p><Link className="button button-primary" to="/trips">Back to My Trips</Link></section>
  const tabs = workspace ? ['overview', 'members', 'proposals', 'decisions', 'checklist', 'chat', 'notifications'] : ['overview']
  const currentMember = workspace?.members.find(member => member.user_id === user?.id)
  return <section className="page-container trips-page"><div className="page-title-row"><div><Link to="/trips" className="text-button">← My trips</Link><p className="eyebrow">{workspace ? 'Group workspace' : 'Saved trip'}</p><h1>{trip.destination}</h1><p className="page-lede">Created {new Date(trip.created_at).toLocaleDateString()}</p></div><div>{!workspace && <button className="button button-primary" onClick={convert}>Convert to group</button>}<button className="button button-quiet" onClick={remove}>Delete trip</button></div></div>{message && <p className="page-lede" role="status">{message}</p>}{workspace && <nav className="trip-tabs" aria-label="Trip workspace"><div>{tabs.map(item => <button key={item} className={tab === item ? 'button button-primary' : 'button button-quiet'} onClick={() => setTab(item)}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div></nav>}{tab === 'overview' && (workspace ? <><GroupOverview workspace={workspace} onOpenTab={setTab} /><PlanCard plan={tripToPlan(trip)} onRegenerate={regenerate} /></> : <PlanCard plan={tripToPlan(trip)} onRegenerate={regenerate} />)}{tab === 'members' && <GroupMembers workspace={workspace} user={user} inviteEmail={inviteEmail} setInviteEmail={setInviteEmail} invite={invite} leave={leave} transfer={transfer} updateMember={updateMember} removeMember={removeMember} />} {tab === 'members' && workspace && <GroupInvitations invitations={invitations} revokeInvitation={revokeInvitation} />}{tab === 'proposals' && <GroupProposals proposals={proposals} results={proposalResults} createProposal={createProposal} vote={(id, choice) => mutateProposal(proposalsApi.vote, id, choice).then(() => setMessage('Vote recorded.'))} removeVote={id => mutateProposal(proposalsApi.removeVote, id)} close={id => mutateProposal(proposalsApi.close, id)} updateProposal={proposal => mutateProposal(proposalsApi.update, proposal.id, { title: window.prompt('Proposal title', proposal.title) || proposal.title })} canManage={currentMember?.role !== 'member'} finalize={id => proposalsApi.finalize(id).then(() => setTab('decisions')).catch(err => setError(err.message))} />}{tab === 'checklist' && <GroupChecklist checklist={checklist} workspace={workspace} draft={draft} setDraft={setDraft} description={checklistDescription} setDescription={setChecklistDescription} assignee={checklistAssignee} setAssignee={setChecklistAssignee} dueAt={checklistDueAt} setDueAt={setChecklistDueAt} addChecklist={addChecklist} updateChecklist={updateChecklist} editChecklist={editChecklist} assignChecklist={assignChecklist} deleteChecklist={deleteChecklist} filter={checklistFilter} setFilter={setChecklistFilter} loading={sectionLoading} error={error} />}{tab === 'chat' && <GroupChat messages={messages} draft={draft} setDraft={setDraft} sendMessage={sendMessage} editMessage={editMessage} deleteMessage={deleteMessage} loadOlder={loadOlderMessages} hasMore={Boolean(messageCursor)} loading={sectionLoading} error={error} canChat={Boolean(currentMember)} userId={user?.id} canModerate={currentMember?.role === 'owner' || currentMember?.role === 'admin'} />}{tab === 'decisions' && <GroupDecisions decisions={decisions} applyDecision={applyDecision} replanDecision={replanDecision} />}{tab === 'notifications' && <GroupNotifications notifications={notifications} readAll={readAllNotifications} read={readNotification} openNotification={openNotification} loading={sectionLoading} error={error} />}</section>
}