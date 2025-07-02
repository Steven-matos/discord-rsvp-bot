# 🧪 Discord RSVP Bot - Testing Guide

This guide walks you through testing all the bot's functionality, including daily event posting, RSVP tracking, and the 2 reminder systems.

## 📋 Prerequisites

Before testing, make sure you have:
- ✅ Bot running and online
- ✅ Weekly schedule setup completed (`/setup_weekly_schedule`)
- ✅ Event channel configured (`/set_event_channel`)
- ✅ Proper Discord permissions (Manage Server)

## 🚀 Quick Test Sequence

Follow this order for complete testing:

### 1. **Set Up Your Server** (One-time setup)

```
/setup_weekly_schedule
```
- Complete all 7 days of the week
- Fill in realistic event data for testing

```
/set_event_channel #your-events-channel
```
- Choose a channel where events will be posted
- Bot needs Send Messages permission in this channel

---

### 2. **Test Daily Event Posting**

```
/test_daily_event
```

**What should happen:**
- ✅ Event posted in your designated channel
- ✅ Beautiful embed with today's event details
- ✅ Three RSVP buttons: ✅ Yes, ❌ No, ❓ Maybe
- ✅ Event shows today's day of the week data

**What to check:**
- Event name, outfit, and vehicle match your schedule
- Buttons are clickable and responsive
- Date shows correctly

---

### 3. **Test RSVP Functionality**

**Click each RSVP button:**
- Click ✅ **Yes** button
- Click ❌ **No** button  
- Click ❓ **Maybe** button

**What should happen:**
- ✅ Bot responds with confirmation message (only you can see)
- ✅ Your RSVP is saved to database
- ✅ You can change your response by clicking different buttons

**Advanced RSVP testing:**
- Have multiple server members click buttons
- Change your RSVP multiple times
- Test with different Discord roles

---

### 4. **View RSVP Results**

```
/view_rsvps
```

**What should happen:**
- ✅ Shows summary of all RSVPs for today's event
- ✅ Lists users under "Attending", "Maybe", "Not Attending"
- ✅ Shows total response count
- ✅ Updates when people change their RSVPs

---

### 5. **Test Reminder System** (The 2 reminders you asked about!)

```
/test_reminder
```

**What should happen:**
- ✅ Bot confirms test is starting
- ✅ **First Reminder** after 10 seconds: "Event starts in 1 hour!"
- ✅ **Second Reminder** after 20 seconds: "Final reminder - 15 minutes!"
- ✅ Both reminders tag @everyone
- ✅ Reminders show event details (outfit, vehicle)

**What this simulates:**
- In production, these would be sent at actual event times
- First reminder: 1 hour before event
- Second reminder: 15 minutes before event

---

## 🔄 Automatic Daily Posting

The bot automatically posts events at **9:00 AM UTC** daily. To test this without waiting:

### Option 1: Manual Test
```
/test_daily_event
```

### Option 2: Change Server Time
1. Temporarily change your server timezone
2. Wait for the next 9:00 AM UTC
3. Verify automatic posting works

---

## 🐛 Troubleshooting Common Issues

### **"No Event Channel Set"**
**Solution:** Run `/set_event_channel #your-channel`

### **"No Event Posted Today"**
**Solution:** 
1. Run `/test_daily_event` first
2. Make sure today's day has schedule data
3. Check if weekly schedule is complete

### **RSVP Buttons Not Working**
**Solution:**
1. Restart the bot (persistent views will reload)
2. Check bot has "Use Application Commands" permission
3. Try clicking the button again

### **"No Schedule for Today"**
**Solution:**
1. Check which day of the week it is
2. Verify you set up that day in `/setup_weekly_schedule`
3. Check database has the day's data

### **Reminders Not Showing Event Data**
**Solution:**
1. Make sure today's day is configured in your schedule
2. Run `/test_daily_event` first to create today's event
3. Check that the event channel is properly set

---

## 📊 Production Testing Checklist

### Daily Event Posting ✅
- [ ] Events post automatically at 9 AM UTC
- [ ] Correct day's event is posted
- [ ] Embed formatting looks good
- [ ] RSVP buttons appear and work

### RSVP System ✅
- [ ] Users can click Yes/No/Maybe
- [ ] Responses are saved to database
- [ ] Users can change their responses
- [ ] Admin can view RSVP summary
- [ ] RSVP counts are accurate

### Reminder System ✅
- [ ] **First reminder** sent 1 hour before event
- [ ] **Second reminder** sent 15 minutes before event
- [ ] Reminders include event details
- [ ] @everyone notifications work
- [ ] Reminders only sent if event exists

### Persistence ✅
- [ ] RSVP buttons work after bot restart
- [ ] Database connections are stable
- [ ] No memory leaks from persistent views

---

## 🎯 Full Test Scenario

**Complete end-to-end test:**

1. **Setup Phase**
   ```
   /setup_weekly_schedule
   /set_event_channel #events
   ```

2. **Daily Event Test**
   ```
   /test_daily_event
   ```

3. **RSVP Test**
   - Click all three buttons
   - Have 2-3 people RSVP
   ```
   /view_rsvps
   ```

4. **Reminder Test**
   ```
   /test_reminder
   ```
   - Wait for both reminders (10 and 20 seconds)

5. **Persistence Test**
   - Restart bot
   - Try clicking RSVP buttons (should still work)

**Expected Result:** ✅ All functionality works smoothly!

---

## 🚨 Important Notes

- **Reminders are @everyone pings** - use in test channel to avoid spam
- **Test reminders are accelerated** (10/20 seconds vs real 1hr/15min)
- **RSVP buttons persist** through bot restarts
- **One RSVP per user per event** - changing response updates the existing one
- **Events post based on current day** - if it's Tuesday, you'll see Tuesday's event

---

## 📞 Need Help?

If any tests fail:
1. Check the bot's console output for errors
2. Verify your database connection is working
3. Ensure all slash commands are synced
4. Check bot permissions in Discord
5. Try restarting the bot if persistent views aren't loading

The system is now fully functional for daily event posting, RSVP tracking, and dual reminder notifications! 