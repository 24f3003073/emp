// Admin pages.

const AdminDashboard = {
  data() { return { s: null, charts: [], running: '' }; },
  template: `
  <div>
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Admin dashboard</h4>
      <div>
        <button class="btn btn-outline-primary btn-sm me-2" :disabled="running" @click="job('reminders')">Send daily reminders now</button>
        <button class="btn btn-outline-primary btn-sm" :disabled="running" @click="job('monthly-report')">Send monthly report now</button>
      </div>
    </div>
    <div class="row g-3 mb-4" v-if="s">
      <div class="col-6 col-md-3" v-for="c in cards" :key="c[0]">
        <div class="card stat-card shadow-sm h-100"><div class="card-body">
          <div class="text-muted small">{{ c[0] }}</div><div class="display-6">{{ s[c[1]] }}</div>
        </div></div>
      </div>
    </div>
    <div class="row g-3">
      <div class="col-lg-4"><div class="card shadow-sm"><div class="card-body">
        <h6>Popular examinations</h6><div class="chart-box"><canvas ref="c1"></canvas></div></div></div></div>
      <div class="col-lg-4"><div class="card shadow-sm"><div class="card-body">
        <h6>Examiner workload</h6><div class="chart-box"><canvas ref="c2"></canvas></div></div></div></div>
      <div class="col-lg-4"><div class="card shadow-sm"><div class="card-body">
        <h6>Bookings, last 30 days</h6><div class="chart-box"><canvas ref="c3"></canvas></div></div></div></div>
    </div>
  </div>`,
  computed: {
    cards() {
      return [['Courses', 'courses'], ['Examinations', 'exams'], ['Students', 'students'],
              ['Examiners', 'examiners'], ['Slots', 'slots'], ['Bookings', 'bookings'],
              ['Active bookings', 'active_bookings'], ['Pending evaluations', 'pending_evaluations']];
    },
  },
  async mounted() {
    try {
      const [s, r] = await Promise.all([api('/admin/dashboard'), api('/admin/reports')]);
      this.s = s;
      this.$nextTick(() => this.draw(r));
    } catch (e) { toast(e.message, 'danger'); }
  },
  beforeUnmount() { this.charts.forEach(c => c.destroy()); },
  methods: {
    draw(r) {
      const bar = (ref, rows, label) => new Chart(this.$refs[ref], {
        type: 'bar',
        data: { labels: rows.map(x => x.name), datasets: [{ label, data: rows.map(x => x.count), backgroundColor: '#0d6efd' }] },
        options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
      });
      this.charts = [
        bar('c1', r.popular_exams, 'Bookings'),
        bar('c2', r.examiner_workload, 'Students'),
        new Chart(this.$refs.c3, {
          type: 'line',
          data: { labels: r.booking_trend.labels.map(d => d.slice(5)), datasets: [{ label: 'Bookings', data: r.booking_trend.values, borderColor: '#198754', tension: 0.3 }] },
          options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
        }),
      ];
    },
    async job(name) {
      this.running = name;
      try { const d = await api('/admin/jobs/' + name, 'POST'); toast(d.message + ' (check the outbox/ folder)'); }
      catch (e) { toast(e.message, 'danger'); } finally { this.running = ''; }
    },
  },
};

const AdminCourses = {
  data() { return { rows: [], q: '', form: this.blank(), editing: null, show: false }; },
  template: `
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Courses</h4>
      <button class="btn btn-primary btn-sm" @click="openNew">+ New course</button>
    </div>
    <div class="card shadow-sm mb-3" v-if="show"><div class="card-body">
      <form class="row g-2" @submit.prevent="save">
        <div class="col-md-3"><label class="form-label">Code</label>
          <input class="form-control" v-model.trim="form.code" required maxlength="30"></div>
        <div class="col-md-5"><label class="form-label">Name</label>
          <input class="form-control" v-model.trim="form.name" required></div>
        <div class="col-md-4"><label class="form-label">Status</label>
          <select class="form-select" v-model="form.status"><option>Active</option><option>Inactive</option></select></div>
        <div class="col-12"><label class="form-label">Description</label>
          <textarea class="form-control" rows="2" v-model="form.description"></textarea></div>
        <div class="col-12">
          <button class="btn btn-primary btn-sm me-2">{{ editing ? 'Update' : 'Create' }}</button>
          <button type="button" class="btn btn-light btn-sm" @click="show = false">Cancel</button></div>
      </form>
    </div></div>
    <input class="form-control mb-3" placeholder="Search by code or name" v-model="q" @input="load">
    <div class="table-responsive"><table class="table table-sm table-hover bg-white">
      <thead><tr><th>Code</th><th>Name</th><th>Description</th><th>Exams</th><th>Status</th><th></th></tr></thead>
      <tbody>
        <tr v-for="c in rows" :key="c.id">
          <td>{{ c.code }}</td><td>{{ c.name }}</td><td class="small">{{ c.description }}</td><td>{{ c.exam_count }}</td>
          <td><span :class="badge(c.status)">{{ c.status }}</span></td>
          <td class="text-end">
            <button class="btn btn-outline-primary btn-sm me-1" @click="edit(c)">Edit</button>
            <button class="btn btn-outline-danger btn-sm" @click="remove(c)">Remove</button></td>
        </tr>
        <tr v-if="!rows.length"><td colspan="6" class="text-center text-muted">No courses yet</td></tr>
      </tbody></table></div>
  </div>`,
  mounted() { this.load(); },
  methods: {
    blank() { return { code: '', name: '', description: '', status: 'Active' }; },
    async load() { try { this.rows = await api('/admin/courses?q=' + encodeURIComponent(this.q)); } catch (e) { toast(e.message, 'danger'); } },
    openNew() { this.form = this.blank(); this.editing = null; this.show = true; },
    edit(c) { this.form = { ...c }; this.editing = c.id; this.show = true; window.scrollTo(0, 0); },
    async save() {
      try {
        if (this.editing) await api('/admin/courses/' + this.editing, 'PUT', this.form);
        else await api('/admin/courses', 'POST', this.form);
        toast('Course saved'); this.show = false; this.load();
      } catch (e) { toast(e.message, 'danger'); }
    },
    async remove(c) {
      if (!confirm('Remove course ' + c.code + '?')) return;
      try { const d = await api('/admin/courses/' + c.id, 'DELETE'); toast(d.message); this.load(); }
      catch (e) { toast(e.message, 'danger'); }
    },
  },
};

const AdminExams = {
  data() {
    return {
      rows: [], courses: [], examiners: [], q: '', status: '', form: this.blank(), editing: null, show: false,
      openId: null, assign: [], rub: { criterion_name: '', max_marks: '', weightage: 1, description: '' },
      types: EXAM_TYPES, statuses: ['Draft', 'Slot Creation', 'Booking Open', 'Closed', 'Completed'],
    };
  },
  template: `
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Examinations</h4>
      <button class="btn btn-primary btn-sm" @click="openNew">+ New examination</button>
    </div>

    <div class="card shadow-sm mb-3" v-if="show"><div class="card-body">
      <form class="row g-2" @submit.prevent="save">
        <div class="col-md-4"><label class="form-label">Course</label>
          <select class="form-select" v-model="form.course_id" required>
            <option value="" disabled>Select course</option>
            <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.code }} - {{ c.name }}</option></select></div>
        <div class="col-md-4"><label class="form-label">Examination name</label>
          <input class="form-control" v-model.trim="form.name" required></div>
        <div class="col-md-4"><label class="form-label">Type</label>
          <select class="form-select" v-model="form.exam_type" required><option v-for="t in types" :key="t">{{ t }}</option></select></div>
        <div class="col-md-3"><label class="form-label">Duration (minutes)</label>
          <input type="number" min="1" class="form-control" v-model.number="form.duration_min" required></div>
        <div class="col-md-3"><label class="form-label">Maximum marks</label>
          <input type="number" min="1" class="form-control" v-model.number="form.max_marks" required></div>
        <div class="col-12"><hr class="my-1"><span class="small text-muted">Timelines (the Open / Close buttons also control each stage)</span></div>
        <div class="col-6 col-md-3"><label class="form-label">Slot creation start</label>
          <input type="date" class="form-control" v-model="form.slot_create_start"></div>
        <div class="col-6 col-md-3"><label class="form-label">Slot creation end</label>
          <input type="date" class="form-control" v-model="form.slot_create_end" :min="form.slot_create_start"></div>
        <div class="col-6 col-md-3"><label class="form-label">Booking start</label>
          <input type="date" class="form-control" v-model="form.booking_start"></div>
        <div class="col-6 col-md-3"><label class="form-label">Booking end (cancel deadline)</label>
          <input type="date" class="form-control" v-model="form.booking_end" :min="form.booking_start"></div>
        <div class="col-12"><label class="form-label">Instructions for students</label>
          <textarea class="form-control" rows="2" v-model="form.instructions"></textarea></div>
        <div class="col-12">
          <button class="btn btn-primary btn-sm me-2">{{ editing ? 'Update' : 'Create' }}</button>
          <button type="button" class="btn btn-light btn-sm" @click="show = false">Cancel</button></div>
      </form>
    </div></div>

    <div class="row g-2 mb-3">
      <div class="col-md-8"><input class="form-control" placeholder="Search examination or course" v-model="q" @input="load"></div>
      <div class="col-md-4"><select class="form-select" v-model="status" @change="load">
        <option value="">All statuses</option><option v-for="s in statuses" :key="s">{{ s }}</option></select></div>
    </div>

    <div class="table-responsive"><table class="table table-sm bg-white">
      <thead><tr><th>Examination</th><th>Type</th><th>Status</th><th>Slot creation</th><th>Booking</th><th></th></tr></thead>
      <tbody v-for="e in rows" :key="e.id">
        <tr>
          <td><b>{{ e.name }}</b><div class="small text-muted">{{ e.course_code }} - {{ e.max_marks }} marks, {{ e.duration_min }} min</div></td>
          <td>{{ e.exam_type }}</td>
          <td><span :class="badge(e.status)">{{ e.status }}</span>
            <span class="badge bg-success ms-1" v-if="e.results_published">Results published</span></td>
          <td class="small">{{ fdate(e.slot_create_start) }} to {{ fdate(e.slot_create_end) }}<br>
            <button class="btn btn-sm py-0" :class="e.slot_creation_open ? 'btn-danger' : 'btn-outline-success'" @click="toggle(e, 'slot-creation', !e.slot_creation_open)">
              {{ e.slot_creation_open ? 'Close' : 'Open' }}</button></td>
          <td class="small">{{ fdate(e.booking_start) }} to {{ fdate(e.booking_end) }}<br>
            <button class="btn btn-sm py-0" :class="e.booking_open ? 'btn-danger' : 'btn-outline-success'" @click="toggle(e, 'booking', !e.booking_open)">
              {{ e.booking_open ? 'Close' : 'Open' }}</button></td>
          <td class="text-end text-nowrap">
            <button class="btn btn-outline-secondary btn-sm me-1" @click="manage(e)">Rubric / examiners</button>
            <button class="btn btn-outline-primary btn-sm me-1" @click="edit(e)">Edit</button>
            <button class="btn btn-outline-danger btn-sm" @click="remove(e)">Delete</button></td>
        </tr>
        <tr v-if="openId === e.id"><td colspan="6" class="bg-light">
          <div class="row g-3">
            <div class="col-lg-7">
              <h6>Rubric criteria</h6>
              <table class="table table-sm bg-white mb-2"><thead><tr><th>Criterion</th><th>Max</th><th>Weight</th><th></th></tr></thead>
                <tbody>
                  <tr v-for="r in e.rubrics" :key="r.id"><td>{{ r.criterion_name }}<div class="small text-muted">{{ r.description }}</div></td>
                    <td>{{ r.max_marks }}</td><td>{{ r.weightage }}</td>
                    <td><button class="btn btn-link btn-sm text-danger p-0" @click="delRubric(r)">remove</button></td></tr>
                  <tr v-if="!e.rubrics.length"><td colspan="4" class="text-muted">No criteria yet</td></tr>
                </tbody></table>
              <form class="row g-2" @submit.prevent="addRubric(e)">
                <div class="col-sm-4"><input class="form-control form-control-sm" placeholder="Criterion" v-model.trim="rub.criterion_name" required></div>
                <div class="col-sm-2"><input type="number" min="0.01" step="any" class="form-control form-control-sm" placeholder="Max" v-model="rub.max_marks" required></div>
                <div class="col-sm-2"><input type="number" min="0" step="any" class="form-control form-control-sm" placeholder="Weight" v-model="rub.weightage"></div>
                <div class="col-sm-4"><input class="form-control form-control-sm" placeholder="Description" v-model.trim="rub.description"></div>
                <div class="col-12"><button class="btn btn-sm btn-primary">Add criterion</button></div>
              </form>
            </div>
            <div class="col-lg-5">
              <h6>Assigned examiners</h6>
              <div class="form-check" v-for="x in examiners" :key="x.id">
                <input class="form-check-input" type="checkbox" :id="'x' + x.id" :value="x.id" v-model="assign">
                <label class="form-check-label" :for="'x' + x.id">{{ x.name }} <span class="small text-muted">{{ x.department }}</span></label></div>
              <div class="text-muted small" v-if="!examiners.length">Add examiners first.</div>
              <button class="btn btn-sm btn-primary mt-2" @click="saveExaminers(e)">Save examiners</button>
              <hr>
              <button class="btn btn-sm me-2" :class="e.results_published ? 'btn-warning' : 'btn-success'" @click="publish(e)">
                {{ e.results_published ? 'Unpublish results' : 'Publish results' }}</button>
              <button class="btn btn-sm btn-outline-dark" v-if="e.status !== 'Completed'" @click="complete(e)">Mark completed</button>
              <button class="btn btn-sm btn-outline-dark" v-else @click="reopen(e)">Reopen</button>
            </div>
          </div>
        </td></tr>
      </tbody>
      <tbody v-if="!rows.length"><tr><td colspan="6" class="text-center text-muted">No examinations found</td></tr></tbody>
    </table></div>
  </div>`,
  async mounted() {
    this.load();
    try { [this.courses, this.examiners] = await Promise.all([api('/admin/courses'), api('/admin/examiners')]); }
    catch (e) { toast(e.message, 'danger'); }
  },
  methods: {
    blank() {
      return { course_id: '', name: '', exam_type: 'Viva', duration_min: 15, max_marks: 100, instructions: '',
               slot_create_start: '', slot_create_end: '', booking_start: '', booking_end: '' };
    },
    async load() {
      try { this.rows = await api('/admin/exams?q=' + encodeURIComponent(this.q) + '&status=' + encodeURIComponent(this.status)); }
      catch (e) { toast(e.message, 'danger'); }
    },
    openNew() { this.form = this.blank(); this.editing = null; this.show = true; },
    edit(e) { this.form = { ...e }; this.editing = e.id; this.show = true; window.scrollTo(0, 0); },
    async save() {
      try {
        if (this.editing) await api('/admin/exams/' + this.editing, 'PUT', this.form);
        else await api('/admin/exams', 'POST', this.form);
        toast('Examination saved'); this.show = false; this.load();
      } catch (e) { toast(e.message, 'danger'); }
    },
    async remove(e) {
      if (!confirm('Delete examination "' + e.name + '"?')) return;
      try { const d = await api('/admin/exams/' + e.id, 'DELETE'); toast(d.message); this.load(); }
      catch (err) { toast(err.message, 'danger'); }
    },
    manage(e) { this.openId = this.openId === e.id ? null : e.id; this.assign = [...e.examiner_ids]; },
    async toggle(e, what, open) {
      try { await api('/admin/exams/' + e.id + '/' + what, 'POST', { open }); toast('Updated'); this.load(); }
      catch (err) { toast(err.message, 'danger'); }
    },
    async saveExaminers(e) {
      try { await api('/admin/exams/' + e.id + '/examiners', 'PUT', { examiner_ids: this.assign }); toast('Examiners saved'); this.load(); }
      catch (err) { toast(err.message, 'danger'); }
    },
    async addRubric(e) {
      try {
        await api('/admin/exams/' + e.id + '/rubrics', 'POST', this.rub);
        this.rub = { criterion_name: '', max_marks: '', weightage: 1, description: '' };
        this.load();
      } catch (err) { toast(err.message, 'danger'); }
    },
    async delRubric(r) {
      try { await api('/admin/rubrics/' + r.id, 'DELETE'); this.load(); } catch (err) { toast(err.message, 'danger'); }
    },
    async publish(e) {
      const publish = !e.results_published;
      if (!confirm((publish ? 'Publish' : 'Unpublish') + ' results for "' + e.name + '"?')) return;
      try {
        const d = await api('/admin/exams/' + e.id + '/publish', 'POST', { publish });
        toast((publish ? 'Published. ' : 'Unpublished. ') + d.evaluated + ' evaluated, ' + d.pending + ' pending.'); this.load();
      } catch (err) { toast(err.message, 'danger'); }
    },
    async complete(e) { try { await api('/admin/exams/' + e.id + '/status', 'PUT', { status: 'Completed' }); this.load(); } catch (err) { toast(err.message, 'danger'); } },
    async reopen(e) { try { await api('/admin/exams/' + e.id + '/status', 'PUT', { status: 'Reopen' }); this.load(); } catch (err) { toast(err.message, 'danger'); } },
  },
};

const AdminExaminers = {
  data() { return { rows: [], q: '', form: this.blank(), editing: null, show: false }; },
  template: `
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Examiners</h4>
      <button class="btn btn-primary btn-sm" @click="openNew">+ Add examiner</button>
    </div>
    <div class="card shadow-sm mb-3" v-if="show"><div class="card-body">
      <form class="row g-2" @submit.prevent="save">
        <div class="col-md-4"><label class="form-label">Name</label><input class="form-control" v-model.trim="form.name" required></div>
        <div class="col-md-4"><label class="form-label">Email</label>
          <input type="email" class="form-control" v-model.trim="form.email" required :disabled="editing"></div>
        <div class="col-md-4"><label class="form-label">{{ editing ? 'New password (optional)' : 'Password' }}</label>
          <input type="password" class="form-control" v-model="form.password" minlength="6" :required="!editing"></div>
        <div class="col-md-4"><label class="form-label">Department</label><input class="form-control" v-model.trim="form.department"></div>
        <div class="col-md-4"><label class="form-label">Phone</label><input class="form-control" v-model.trim="form.phone"></div>
        <div class="col-md-4"><label class="form-label">Contact details</label><input class="form-control" v-model.trim="form.contact_details"></div>
        <div class="col-12">
          <button class="btn btn-primary btn-sm me-2">{{ editing ? 'Update' : 'Create examiner' }}</button>
          <button type="button" class="btn btn-light btn-sm" @click="show = false">Cancel</button></div>
      </form>
    </div></div>
    <input class="form-control mb-3" placeholder="Search by name or email" v-model="q" @input="load">
    <div class="table-responsive"><table class="table table-sm table-hover bg-white">
      <thead><tr><th>Name</th><th>Email</th><th>Department</th><th>Contact</th><th>Status</th><th></th></tr></thead>
      <tbody>
        <tr v-for="u in rows" :key="u.id">
          <td>{{ u.name }}</td><td>{{ u.email }}</td><td>{{ u.department }}</td><td>{{ u.contact_details }}</td>
          <td><span :class="badge(u.is_active ? 'Active' : 'Inactive')">{{ u.is_active ? 'Active' : 'Inactive' }}</span></td>
          <td class="text-end text-nowrap">
            <button class="btn btn-outline-primary btn-sm me-1" @click="edit(u)">Edit</button>
            <button class="btn btn-outline-secondary btn-sm" @click="toggle(u)">{{ u.is_active ? 'Deactivate' : 'Activate' }}</button></td>
        </tr>
        <tr v-if="!rows.length"><td colspan="6" class="text-center text-muted">No examiners yet</td></tr>
      </tbody></table></div>
  </div>`,
  mounted() { this.load(); },
  methods: {
    blank() { return { name: '', email: '', password: '', phone: '', department: '', contact_details: '' }; },
    async load() { try { this.rows = await api('/admin/examiners?q=' + encodeURIComponent(this.q)); } catch (e) { toast(e.message, 'danger'); } },
    openNew() { this.form = this.blank(); this.editing = null; this.show = true; },
    edit(u) { this.form = { ...this.blank(), ...u, password: '' }; this.editing = u.id; this.show = true; window.scrollTo(0, 0); },
    async save() {
      try {
        if (this.editing) await api('/admin/examiners/' + this.editing, 'PUT', this.form);
        else await api('/admin/examiners', 'POST', this.form);
        toast('Examiner saved'); this.show = false; this.load();
      } catch (e) { toast(e.message, 'danger'); }
    },
    async toggle(u) {
      try { await api('/admin/examiners/' + u.id, 'PUT', { is_active: !u.is_active }); this.load(); } catch (e) { toast(e.message, 'danger'); }
    },
  },
};

const AdminStudents = {
  data() { return { rows: [], q: '' }; },
  template: `
  <div>
    <h4 class="mb-3">Students</h4>
    <input class="form-control mb-3" placeholder="Search by name, email or phone" v-model="q" @input="load">
    <div class="table-responsive"><table class="table table-sm table-hover bg-white">
      <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Bookings</th><th>Status</th><th></th></tr></thead>
      <tbody>
        <tr v-for="u in rows" :key="u.id">
          <td>{{ u.name }}</td><td>{{ u.email }}</td><td>{{ u.phone }}</td><td>{{ u.bookings }}</td>
          <td><span :class="badge(u.is_active ? 'Active' : 'Inactive')">{{ u.is_active ? 'Active' : 'Inactive' }}</span></td>
          <td class="text-end"><button class="btn btn-outline-secondary btn-sm" @click="toggle(u)">{{ u.is_active ? 'Deactivate' : 'Activate' }}</button></td>
        </tr>
        <tr v-if="!rows.length"><td colspan="6" class="text-center text-muted">No students found</td></tr>
      </tbody></table></div>
  </div>`,
  mounted() { this.load(); },
  methods: {
    async load() { try { this.rows = await api('/admin/students?q=' + encodeURIComponent(this.q)); } catch (e) { toast(e.message, 'danger'); } },
    async toggle(u) { try { await api('/admin/students/' + u.id, 'PUT', { is_active: !u.is_active }); this.load(); } catch (e) { toast(e.message, 'danger'); } },
  },
};

const AdminSlots = {
  data() {
    return { rows: [], exams: [], examiners: [], examId: '', examinerId: '', date: '', edit: null, newExaminer: '' };
  },
  template: `
  <div>
    <h4 class="mb-3">All examiner slots</h4>
    <div class="row g-2 mb-3">
      <div class="col-md-4"><select class="form-select" v-model="examId" @change="load">
        <option value="">All examinations</option><option v-for="e in exams" :key="e.id" :value="e.id">{{ e.name }}</option></select></div>
      <div class="col-md-4"><select class="form-select" v-model="examinerId" @change="load">
        <option value="">All examiners</option><option v-for="x in examiners" :key="x.id" :value="x.id">{{ x.name }}</option></select></div>
      <div class="col-md-4"><input type="date" class="form-control" v-model="date" @change="load"></div>
    </div>
    <div class="card shadow-sm mb-3" v-if="edit"><div class="card-body">
      <h6>Reschedule slot #{{ edit.id }} (exceptional change)</h6>
      <form class="row g-2" @submit.prevent="save">
        <div class="col-md-3"><label class="form-label">Date</label><input type="date" class="form-control" v-model="edit.date" required></div>
        <div class="col-6 col-md-2"><label class="form-label">Start</label><input type="time" class="form-control" v-model="edit.start_time" required></div>
        <div class="col-6 col-md-2"><label class="form-label">End</label><input type="time" class="form-control" v-model="edit.end_time" required></div>
        <div class="col-md-2"><label class="form-label">Capacity</label><input type="number" min="1" class="form-control" v-model.number="edit.capacity" required></div>
        <div class="col-md-3"><label class="form-label">Meeting link</label><input class="form-control" v-model.trim="edit.meeting_link"></div>
        <div class="col-12">
          <button class="btn btn-primary btn-sm me-2">Save slot</button>
          <button type="button" class="btn btn-light btn-sm" @click="edit = null">Cancel</button></div>
      </form>
      <hr>
      <div class="row g-2 align-items-end">
        <div class="col-md-5"><label class="form-label">Change assigned examiner</label>
          <select class="form-select" v-model="newExaminer"><option v-for="x in examiners" :key="x.id" :value="x.id">{{ x.name }}</option></select></div>
        <div class="col-md-3"><button class="btn btn-outline-primary btn-sm" @click="changeExaminer">Change examiner</button></div>
      </div>
    </div></div>
    <div class="table-responsive"><table class="table table-sm bg-white">
      <thead><tr><th>Examination</th><th>Examiner</th><th>Date</th><th>Time</th><th>Booked</th><th>Status</th><th></th></tr></thead>
      <tbody>
        <tr v-for="s in rows" :key="s.id">
          <td>{{ s.exam_name }}</td><td>{{ s.examiner_name }}</td><td>{{ s.date }}</td><td>{{ s.start_time }}-{{ s.end_time }}</td>
          <td>{{ s.booked }}/{{ s.capacity }}</td><td><span :class="badge(s.status)">{{ s.status }}</span></td>
          <td class="text-end"><button class="btn btn-outline-primary btn-sm" @click="open(s)">Reschedule / reassign</button></td>
        </tr>
        <tr v-if="!rows.length"><td colspan="7" class="text-center text-muted">No slots found</td></tr>
      </tbody></table></div>
  </div>`,
  async mounted() {
    this.load();
    try { [this.exams, this.examiners] = await Promise.all([api('/admin/exams'), api('/admin/examiners')]); } catch (e) { toast(e.message, 'danger'); }
  },
  methods: {
    async load() {
      const p = new URLSearchParams();
      if (this.examId) p.set('exam_id', this.examId);
      if (this.examinerId) p.set('examiner_id', this.examinerId);
      if (this.date) p.set('date', this.date);
      try { this.rows = await api('/admin/slots?' + p.toString()); } catch (e) { toast(e.message, 'danger'); }
    },
    open(s) { this.edit = { ...s }; this.newExaminer = s.examiner_id; window.scrollTo(0, 0); },
    async save() {
      try { await api('/admin/slots/' + this.edit.id, 'PUT', this.edit); toast('Slot updated, booked students were notified'); this.edit = null; this.load(); }
      catch (e) { toast(e.message, 'danger'); }
    },
    async changeExaminer() {
      try { await api('/admin/slots/' + this.edit.id + '/examiner', 'PUT', { examiner_id: this.newExaminer }); toast('Examiner changed'); this.edit = null; this.load(); }
      catch (e) { toast(e.message, 'danger'); }
    },
  },
};

const AdminBookings = {
  data() { return { rows: [], exams: [], q: '', examId: '', status: '', moving: null, slots: [], newSlot: '' }; },
  template: `
  <div>
    <h4 class="mb-3">All bookings</h4>
    <div class="row g-2 mb-3">
      <div class="col-md-5"><input class="form-control" placeholder="Search student or examination" v-model="q" @input="load"></div>
      <div class="col-md-4"><select class="form-select" v-model="examId" @change="load">
        <option value="">All examinations</option><option v-for="e in exams" :key="e.id" :value="e.id">{{ e.name }}</option></select></div>
      <div class="col-md-3"><select class="form-select" v-model="status" @change="load">
        <option value="">All statuses</option><option>Booked</option><option>Completed</option><option>Cancelled</option></select></div>
    </div>
    <div class="card shadow-sm mb-3" v-if="moving"><div class="card-body">
      <h6>Reschedule {{ moving.student_name }} for {{ moving.exam_name }}</h6>
      <div class="row g-2 align-items-end">
        <div class="col-md-7"><label class="form-label">Move to slot (this also reassigns the examiner)</label>
          <select class="form-select" v-model="newSlot">
            <option value="" disabled>Select a slot with free seats</option>
            <option v-for="s in slots" :key="s.id" :value="s.id">{{ s.date }} {{ s.start_time }}-{{ s.end_time }} - {{ s.examiner_name }} ({{ s.available_seats }} free)</option></select></div>
        <div class="col-md-5">
          <button class="btn btn-primary btn-sm me-2" :disabled="!newSlot" @click="move">Move booking</button>
          <button class="btn btn-light btn-sm" @click="moving = null">Cancel</button></div>
      </div>
    </div></div>
    <div class="table-responsive"><table class="table table-sm bg-white">
      <thead><tr><th>Student</th><th>Examination</th><th>Date and time</th><th>Examiner</th><th>Status</th><th></th></tr></thead>
      <tbody>
        <tr v-for="b in rows" :key="b.id">
          <td>{{ b.student_name }}<div class="small text-muted">{{ b.student_email }}</div></td>
          <td>{{ b.exam_name }}</td><td>{{ b.date }} {{ b.start_time }}</td><td>{{ b.examiner_name }}</td>
          <td><span :class="badge(b.status)">{{ b.status }}</span></td>
          <td class="text-end text-nowrap" v-if="b.status === 'Booked' && !b.evaluated">
            <button class="btn btn-outline-primary btn-sm me-1" @click="startMove(b)">Reschedule</button>
            <button class="btn btn-outline-danger btn-sm" @click="cancel(b)">Cancel</button></td>
          <td v-else></td>
        </tr>
        <tr v-if="!rows.length"><td colspan="6" class="text-center text-muted">No bookings found</td></tr>
      </tbody></table></div>
  </div>`,
  async mounted() {
    this.load();
    try { this.exams = await api('/admin/exams'); } catch (e) { toast(e.message, 'danger'); }
  },
  methods: {
    async load() {
      const p = new URLSearchParams({ q: this.q, exam_id: this.examId, status: this.status });
      try { this.rows = await api('/admin/bookings?' + p.toString()); } catch (e) { toast(e.message, 'danger'); }
    },
    async startMove(b) {
      this.moving = b; this.newSlot = '';
      try { this.slots = (await api('/admin/slots?exam_id=' + b.exam_id)).filter(s => s.status === 'Available' && s.id !== b.slot_id); }
      catch (e) { toast(e.message, 'danger'); }
    },
    async move() {
      try { await api('/admin/bookings/' + this.moving.id + '/reschedule', 'PUT', { slot_id: this.newSlot }); toast('Booking moved'); this.moving = null; this.load(); }
      catch (e) { toast(e.message, 'danger'); }
    },
    async cancel(b) {
      if (!confirm('Cancel the booking of ' + b.student_name + '?')) return;
      try { await api('/admin/bookings/' + b.id, 'DELETE'); toast('Booking cancelled'); this.load(); } catch (e) { toast(e.message, 'danger'); }
    },
  },
};

const AdminSearch = {
  data() { return { q: '', r: null }; },
  template: `
  <div>
    <h4 class="mb-3">Search</h4>
    <form class="input-group mb-4" @submit.prevent="go">
      <input class="form-control" placeholder="Students, examiners, examinations, bookings" v-model.trim="q" required minlength="2">
      <button class="btn btn-primary">Search</button>
    </form>
    <div v-if="r">
      <h6>Students ({{ r.students.length }})</h6>
      <ul><li v-for="u in r.students" :key="u.id">{{ u.name }} - {{ u.email }}</li></ul>
      <h6>Examiners ({{ r.examiners.length }})</h6>
      <ul><li v-for="u in r.examiners" :key="u.id">{{ u.name }} - {{ u.email }} {{ u.department }}</li></ul>
      <h6>Examinations ({{ r.exams.length }})</h6>
      <ul><li v-for="e in r.exams" :key="e.id">{{ e.name }} ({{ e.course_code }}) - {{ e.status }}</li></ul>
      <h6>Bookings ({{ r.bookings.length }})</h6>
      <ul><li v-for="b in r.bookings" :key="b.id">{{ b.student_name }} - {{ b.exam_name }} - {{ b.date }} - {{ b.status }}</li></ul>
    </div>
  </div>`,
  methods: {
    async go() { try { this.r = await api('/admin/search?q=' + encodeURIComponent(this.q)); } catch (e) { toast(e.message, 'danger'); } },
  },
};
