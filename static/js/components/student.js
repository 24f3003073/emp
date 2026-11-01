// Student pages.

const StudentDashboard = {
  data() { return { d: null }; },
  template: `
  <div v-if="d">
    <h4 class="mb-3">Student dashboard</h4>
    <div class="row g-3 mb-4">
      <div class="col-6 col-md-3" v-for="c in cards" :key="c[0]">
        <div class="card stat-card shadow-sm h-100"><div class="card-body">
          <div class="text-muted small">{{ c[0] }}</div><div class="display-6">{{ c[1] }}</div></div></div>
      </div>
    </div>
    <div class="row g-3">
      <div class="col-lg-6"><div class="card shadow-sm h-100"><div class="card-body">
        <h6>Upcoming examinations</h6>
        <p class="text-muted small" v-if="!d.upcoming.length">Nothing scheduled.</p>
        <div v-for="b in d.upcoming" :key="b.id" class="border-bottom py-2">
          <b>{{ b.exam_name }}</b> <span class="small text-muted">{{ b.course_code }}</span><br>
          {{ b.date }} {{ b.start_time }}-{{ b.end_time }}, examiner {{ b.examiner_name }}
          <a v-if="b.meeting_link" :href="b.meeting_link" target="_blank" class="small ms-1">Join link</a></div>
      </div></div></div>
      <div class="col-lg-6"><div class="card shadow-sm h-100"><div class="card-body">
        <h6>Open for booking</h6>
        <p class="text-muted small" v-if="!d.available_exams.length">No examinations are open for booking right now.</p>
        <div v-for="e in d.available_exams" :key="e.id" class="border-bottom py-2 d-flex justify-content-between">
          <div><b>{{ e.name }}</b> <span class="small text-muted">{{ e.course_code }}</span>
            <div class="small">Book by {{ fdate(e.booking_end) }} - {{ e.seats_left }} seat(s) left</div></div>
          <router-link class="btn btn-primary btn-sm align-self-center" to="/student/exams">Book</router-link></div>
      </div></div></div>
      <div class="col-12"><div class="card shadow-sm"><div class="card-body">
        <h6>Published results</h6>
        <p class="text-muted small" v-if="!d.results.length">No results published yet.</p>
        <div v-for="r in d.results" :key="r.id" class="py-1">{{ r.exam_name }}: <b>{{ r.total_marks }} / {{ r.max_marks }}</b></div>
        <router-link to="/student/results" v-if="d.results.length" class="small">See feedback</router-link>
      </div></div></div>
    </div>
  </div>`,
  computed: {
    cards() {
      return [['Available examinations', this.d.available_exams.length], ['Available slots', this.d.available_slots.length],
              ['Upcoming', this.d.upcoming.length], ['Results', this.d.results.length]];
    },
  },
  async mounted() { try { this.d = await api('/student/dashboard'); } catch (e) { toast(e.message, 'danger'); } },
};

const StudentExams = {
  data() { return { rows: [], q: '', type: '', course: '', status: '', types: EXAM_TYPES, openId: null, slots: [], loading: false }; },
  computed: {
    courses() {
      const m = {};
      this.rows.forEach(e => { m[e.course_id] = e.course_code + ' - ' + e.course_name; });
      return Object.entries(m);
    },
  },
  template: `
  <div>
    <h4 class="mb-3">Examinations</h4>
    <div class="row g-2 mb-3">
      <div class="col-md-4"><input class="form-control" placeholder="Search examination or course" v-model="q" @input="load"></div>
      <div class="col-md-3"><select class="form-select" v-model="type" @change="load">
        <option value="">All types</option><option v-for="t in types" :key="t">{{ t }}</option></select></div>
      <div class="col-md-3"><select class="form-select" v-model="course" @change="load">
        <option value="">All courses</option><option v-for="c in courses" :key="c[0]" :value="c[0]">{{ c[1] }}</option></select></div>
      <div class="col-md-2"><select class="form-select" v-model="status" @change="load">
        <option value="">Any status</option><option>Booking Open</option><option>Closed</option><option>Completed</option></select></div>
    </div>
    <p class="text-muted" v-if="!rows.length">No examinations found.</p>
    <div class="card exam-card shadow-sm mb-3" v-for="e in rows" :key="e.id"><div class="card-body">
      <div class="d-flex flex-wrap justify-content-between">
        <div><h5 class="mb-0">{{ e.name }}</h5>
          <div class="small text-muted">{{ e.course_code }} - {{ e.course_name }}</div></div>
        <div><span :class="badge(e.status)">{{ e.status }}</span></div>
      </div>
      <div class="small mt-2">{{ e.exam_type }} - {{ e.duration_min }} min - {{ e.max_marks }} marks - Booking {{ fdate(e.booking_start) }} to {{ fdate(e.booking_end) }}</div>
      <div class="small text-muted" v-if="e.instructions">Instructions: {{ e.instructions }}</div>
      <div class="mt-2" v-if="e.my_booking">
        <span class="badge bg-primary">You are booked: {{ e.my_booking.date }} {{ e.my_booking.start_time }} with {{ e.my_booking.examiner_name }}</span></div>
      <div class="mt-2" v-else-if="e.booking_active">
        <button class="btn btn-primary btn-sm" @click="toggleSlots(e)">{{ openId === e.id ? 'Hide slots' : 'View and book slots' }}</button></div>
      <div class="small text-muted mt-2" v-else>Booking is not open at the moment.</div>

      <div class="mt-3" v-if="openId === e.id && !e.my_booking">
        <p class="small text-muted" v-if="!slots.length">No slots available.</p>
        <div class="table-responsive" v-else><table class="table table-sm mb-0">
          <thead><tr><th>Date</th><th>Time</th><th>Examiner</th><th>Seats left</th><th></th></tr></thead>
          <tbody><tr v-for="s in slots" :key="s.id">
            <td>{{ s.date }}</td><td>{{ s.start_time }}-{{ s.end_time }}</td><td>{{ s.examiner_name }}</td>
            <td>{{ s.available_seats }}/{{ s.capacity }}</td>
            <td class="text-end"><button class="btn btn-success btn-sm" :disabled="s.status !== 'Available'" @click="book(s)">
              {{ s.status === 'Available' ? 'Book' : 'Full' }}</button></td></tr></tbody></table></div>
      </div>
    </div></div>
  </div>`,
  mounted() { this.load(); },
  methods: {
    async load() {
      const p = new URLSearchParams({ q: this.q, type: this.type, course_id: this.course, status: this.status });
      try { this.rows = await api('/student/exams?' + p.toString()); } catch (e) { toast(e.message, 'danger'); }
    },
    async toggleSlots(e) {
      if (this.openId === e.id) { this.openId = null; return; }
      try { this.slots = await api('/student/exams/' + e.id + '/slots'); this.openId = e.id; } catch (err) { toast(err.message, 'danger'); }
    },
    async book(s) {
      if (!confirm('Book ' + s.date + ' ' + s.start_time + ' with ' + s.examiner_name + '?')) return;
      try { await api('/student/bookings', 'POST', { slot_id: s.id }); toast('Slot booked'); this.openId = null; this.load(); }
      catch (e) { toast(e.message, 'danger'); this.load(); }
    },
  },
};

const StudentBookings = {
  data() { return { rows: [], exporting: false, file: '', timer: null }; },
  template: `
  <div>
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-3">
      <h4 class="mb-0">My bookings and history</h4>
      <div>
        <button class="btn btn-outline-primary btn-sm" :disabled="exporting" @click="startExport">
          {{ exporting ? 'Preparing CSV...' : 'Export history (CSV)' }}</button>
        <button class="btn btn-success btn-sm ms-2" v-if="file" @click="download">Download ready file</button>
      </div>
    </div>
    <div class="table-responsive"><table class="table table-sm bg-white">
      <thead><tr><th>Examination</th><th>Date and time</th><th>Examiner</th><th>Status</th><th>Marks</th><th></th></tr></thead>
      <tbody>
        <tr v-for="b in rows" :key="b.id">
          <td>{{ b.exam_name }}<div class="small text-muted">{{ b.course_code }} - {{ b.exam_type }}</div></td>
          <td>{{ b.date }} {{ b.start_time }}-{{ b.end_time }}</td><td>{{ b.examiner_name }}</td>
          <td><span :class="badge(b.status)">{{ b.status }}</span></td>
          <td>{{ b.marks !== null ? b.marks + ' / ' + b.max_marks : (b.evaluated ? 'Awaiting publication' : '-') }}</td>
          <td class="text-end"><button class="btn btn-outline-danger btn-sm" v-if="b.status === 'Booked' && !b.evaluated" @click="cancel(b)">Cancel</button></td>
        </tr>
        <tr v-if="!rows.length"><td colspan="6" class="text-center text-muted">No bookings yet</td></tr>
      </tbody></table></div>
  </div>`,
  mounted() { this.load(); },
  beforeUnmount() { clearInterval(this.timer); },
  methods: {
    async load() { try { this.rows = await api('/student/history'); } catch (e) { toast(e.message, 'danger'); } },
    async cancel(b) {
      if (!confirm('Cancel your booking for ' + b.exam_name + '?')) return;
      try { await api('/student/bookings/' + b.id, 'DELETE'); toast('Booking cancelled'); this.load(); } catch (e) { toast(e.message, 'danger'); }
    },
    async startExport() {
      this.exporting = true; this.file = '';
      try {
        const d = await api('/student/export', 'POST');
        toast(d.message, 'info');
        this.timer = setInterval(() => this.check(d.task_id), 2000);
      } catch (e) { toast(e.message, 'danger'); this.exporting = false; }
    },
    async check(id) {
      try {
        const r = await api('/student/export/' + id);
        if (r.state === 'SUCCESS') { clearInterval(this.timer); this.exporting = false; this.file = r.filename; toast('Your CSV export is ready'); }
        else if (r.state === 'FAILURE') { clearInterval(this.timer); this.exporting = false; toast('Export failed', 'danger'); }
      } catch (e) { clearInterval(this.timer); this.exporting = false; toast(e.message, 'danger'); }
    },
    async download() {
      try { await downloadFile('/student/export/download/' + this.file, this.file); } catch (e) { toast(e.message, 'danger'); }
    },
  },
};

const StudentResults = {
  data() { return { rows: null }; },
  template: `
  <div>
    <h4 class="mb-3">Results and feedback</h4>
    <p class="text-muted" v-if="rows && !rows.length">No results have been published yet.</p>
    <div class="card shadow-sm mb-3" v-for="r in rows" :key="r.id"><div class="card-body">
      <div class="d-flex justify-content-between flex-wrap">
        <div><h5 class="mb-0">{{ r.exam_name }}</h5>
          <div class="small text-muted">{{ r.course_code }} - {{ r.date }} - examiner {{ r.examiner_name }}</div></div>
        <div class="text-end"><div class="fs-4 fw-semibold">{{ r.total_marks }} / {{ r.max_marks }}</div>
          <button class="btn btn-outline-primary btn-sm" @click="scorecard(r)">Download scorecard</button></div>
      </div>
      <table class="table table-sm mt-3 mb-2"><tbody>
        <tr v-for="s in r.scores" :key="s.rubric_id"><td>{{ s.criterion_name }}</td><td class="text-end">{{ s.marks }} / {{ s.max_marks }}</td></tr></tbody></table>
      <div><b>Examiner feedback:</b> {{ r.remarks || '-' }}</div>
    </div></div>
  </div>`,
  async mounted() { try { this.rows = await api('/student/results'); } catch (e) { toast(e.message, 'danger'); } },
  methods: {
    async scorecard(r) {
      try { await downloadFile('/student/results/' + r.booking_id + '/scorecard', 'scorecard_' + r.booking_id + '.html'); }
      catch (e) { toast(e.message, 'danger'); }
    },
  },
};
