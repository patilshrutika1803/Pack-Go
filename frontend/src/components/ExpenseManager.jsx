import { useEffect, useState } from 'react'
import { expensesApi } from '../api/client'
import './ExpenseManager.css'

const CATEGORIES = ['accommodation', 'food', 'transport', 'activities', 'shopping', 'other']
const today = () => new Date().toISOString().slice(0, 10)
const currencyAmount = (value, currency) => `${currency} ${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function ExpenseManager({ tripId, members = [], user, currentRole, currency = 'INR' }) {
  const [expenses, setExpenses] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [amount, setAmount] = useState('')
  const [payerId, setPayerId] = useState(user?.id || '')
  const [category, setCategory] = useState('food')
  const [expenseDate, setExpenseDate] = useState(today)
  const [description, setDescription] = useState('')
  const [splitType, setSplitType] = useState('equal')
  const [participantIds, setParticipantIds] = useState([])
  const [shares, setShares] = useState({})
  const [formError, setFormError] = useState('')
  const activeMembers = members.filter(member => !member.status || member.status === 'active')
  const canManage = expense => expense.created_by_user_id === user?.id || ['owner', 'admin'].includes(currentRole)

  const refresh = async () => {
    const [rows, totals] = await Promise.all([expensesApi.list(tripId), expensesApi.summary(tripId)])
    setExpenses(rows)
    setSummary(totals)
  }

  useEffect(() => {
    let active = true
    Promise.all([expensesApi.list(tripId), expensesApi.summary(tripId)])
      .then(([rows, totals]) => { if (active) { setExpenses(rows); setSummary(totals) } })
      .catch(err => { if (active) setError(err.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [tripId])

  const resetForm = () => {
    setEditingId(null)
    setAmount('')
    setPayerId(user?.id || '')
    setCategory('food')
    setExpenseDate(today())
    setDescription('')
    setSplitType('equal')
    setParticipantIds([])
    setShares({})
    setFormError('')
  }

  const startEdit = expense => {
    setEditingId(expense.id)
    setAmount(String(expense.amount))
    setPayerId(expense.payer_user_id)
    setCategory(expense.category)
    setExpenseDate(expense.expense_date)
    setDescription(expense.description || '')
    setSplitType(expense.split_type)
    setParticipantIds(expense.participants.map(item => item.user_id))
    setShares(Object.fromEntries(expense.participants.map(item => [item.user_id, String(item.amount)])))
    setFormError('')
    setNotice('')
  }

  const toggleParticipant = id => {
    setParticipantIds(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id])
    setShares(current => ({ ...current, [id]: current[id] || '' }))
  }

  const submit = async event => {
    event.preventDefault()
    setFormError('')
    setError('')
    const cents = Math.round(Number(amount) * 100)
    if (!Number.isFinite(cents) || cents <= 0 || !/^\d+(\.\d{1,2})?$/.test(amount.trim())) {
      setFormError('Enter an amount greater than zero with at most two decimal places.')
      return
    }
    if (!participantIds.length) {
      setFormError('Choose at least one participant.')
      return
    }
    const participants = splitType === 'equal'
      ? participantIds.map(user_id => ({ user_id }))
      : participantIds.map(user_id => ({ user_id, amount: shares[user_id] }))
    if (splitType === 'custom') {
      const shareCents = participants.map(item => Math.round(Number(item.amount) * 100))
      if (shareCents.some((value, index) => !Number.isFinite(value) || value <= 0 || !/^\d+(\.\d{1,2})?$/.test(String(participants[index].amount || '').trim())) || shareCents.reduce((total, value) => total + value, 0) !== cents) {
        setFormError('Custom participant shares must be valid and add up to the expense amount.')
        return
      }
    }
    setSaving(true)
    try {
      const payload = { amount, payer_user_id: payerId || undefined, category, expense_date: expenseDate, description: description.trim() || null, split_type: splitType, participants }
      if (editingId) await expensesApi.update(editingId, payload)
      else await expensesApi.create(tripId, payload)
      await refresh()
      setNotice(editingId ? 'Expense updated.' : 'Expense added.')
      resetForm()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async expense => {
    if (!window.confirm(`Delete the ${currencyAmount(expense.amount, currency)} expense${expense.description ? ` for ${expense.description}` : ''}?`)) return
    setError('')
    setNotice('')
    try {
      await expensesApi.remove(expense.id)
      await refresh()
      if (editingId === expense.id) resetForm()
      setNotice('Expense deleted.')
    } catch (err) {
      setError(err.message)
    }
  }

  return <section className="expense-manager" aria-labelledby="expense-heading">
    <header className="expense-heading">
      <div><p className="eyebrow">Trip ledger</p><h2 id="expense-heading">Expenses</h2></div>
      {summary && <p className="expense-total"><span>Total recorded</span><strong>{currencyAmount(summary.total_expenses, currency)}</strong></p>}
    </header>
    {error && <p className="form-error" role="alert">{error}</p>}
    {notice && <p className="expense-notice" role="status">{notice}</p>}
    {loading ? <p className="page-lede">Loading expenses...</p> : <>
      {summary && <div className="expense-summary-grid">
        <section><h3>By category</h3>{Object.keys(summary.category_totals).length ? Object.entries(summary.category_totals).map(([name, total]) => <p key={name}><span>{name}</span><strong>{currencyAmount(total, currency)}</strong></p>) : <p className="expense-muted">No category totals yet.</p>}</section>
        <section><h3>By date</h3>{Object.keys(summary.date_totals).length ? Object.entries(summary.date_totals).sort(([left], [right]) => right.localeCompare(left)).map(([date, total]) => <p key={date}><span>{date}</span><strong>{currencyAmount(total, currency)}</strong></p>) : <p className="expense-muted">No date totals yet.</p>}</section>
        <section><h3>Participant balances</h3>{summary.participants.length ? summary.participants.map(person => <p key={person.user_id}><span>{person.name} <small>paid {currencyAmount(person.total_paid, currency)} · owes {currencyAmount(person.total_owed, currency)}</small></span><strong className={Number(person.balance) < 0 ? 'is-negative' : ''}>{Number(person.balance) > 0 ? '+' : ''}{currencyAmount(person.balance, currency)}</strong></p>) : <p className="expense-muted">Balances appear after an expense is added.</p>}</section>
        <section><h3>Suggested settlements</h3>{summary.settlements.length ? summary.settlements.map((settlement, index) => <p key={`${settlement.from_user_id}-${settlement.to_user_id}-${index}`}><span>{settlement.from_name} pays {settlement.to_name}</span><strong>{currencyAmount(settlement.amount, currency)}</strong></p>) : <p className="expense-muted">Everyone is settled.</p>}</section>
      </div>}
      <div className="expense-workspace">
        <section className="expense-list" aria-label="Trip expenses">
          <h3>Recorded expenses</h3>
          {!expenses.length ? <p className="expense-muted">No expenses recorded for this trip.</p> : expenses.map(expense => <article className="expense-row" key={expense.id}>
            <div className="expense-row-main"><strong>{expense.description || expense.category}</strong><span>{expense.expense_date} · {expense.category} · paid by {expense.payer_name}</span><small>{expense.participants.map(person => `${person.name}: ${currencyAmount(person.amount, currency)}`).join(' · ')}</small></div>
            <strong className="expense-row-amount">{currencyAmount(expense.amount, currency)}</strong>
            {canManage(expense) && <div className="expense-actions"><button type="button" onClick={() => startEdit(expense)}>Edit</button><button type="button" onClick={() => remove(expense)}>Delete</button></div>}
          </article>)}
        </section>
        <form className="expense-form" onSubmit={submit}>
          <h3>{editingId ? 'Edit expense' : 'Add expense'}</h3>
          <label>Amount<input inputMode="decimal" type="number" min="0.01" step="0.01" value={amount} onChange={event => setAmount(event.target.value)} required /></label>
          <div className="expense-form-row"><label>Category<select value={category} onChange={event => setCategory(event.target.value)}>{CATEGORIES.map(item => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}</select></label><label>Date<input type="date" value={expenseDate} onChange={event => setExpenseDate(event.target.value)} required /></label></div>
          <label>Description<input maxLength="2000" value={description} onChange={event => setDescription(event.target.value)} placeholder="What was this for?" /></label>
          <label>Payer<select value={payerId} onChange={event => setPayerId(event.target.value)} required>{activeMembers.map(member => <option key={member.user_id} value={member.user_id}>{member.user?.name || (member.user_id === user?.id ? user?.name : member.user_id)}</option>)}</select></label>
          <fieldset><legend>Split</legend><div className="expense-split-options"><label><input type="radio" name="splitType" value="equal" checked={splitType === 'equal'} onChange={() => setSplitType('equal')} /> Equal</label><label><input type="radio" name="splitType" value="custom" checked={splitType === 'custom'} onChange={() => setSplitType('custom')} /> Custom</label></div>
            {activeMembers.map(member => <label className="expense-participant" key={member.user_id}><span><input type="checkbox" checked={participantIds.includes(member.user_id)} onChange={() => toggleParticipant(member.user_id)} />{member.user?.name || (member.user_id === user?.id ? user?.name : member.user_id)}</span>{splitType === 'custom' && participantIds.includes(member.user_id) && <input aria-label={`${member.user?.name || 'Participant'} share`} inputMode="decimal" type="number" min="0.01" step="0.01" value={shares[member.user_id] || ''} onChange={event => setShares(current => ({ ...current, [member.user_id]: event.target.value }))} required />}</label>)}
          </fieldset>
          {formError && <p className="form-error" role="alert">{formError}</p>}
          <div className="expense-form-actions"><button className="button button-primary" type="submit" disabled={saving}>{saving ? 'Saving...' : editingId ? 'Save changes' : 'Add expense'}</button>{editingId && <button className="button button-quiet" type="button" onClick={resetForm}>Cancel</button>}</div>
        </form>
      </div>
    </>}
  </section>
}
