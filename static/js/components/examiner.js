// Examiner pages.

const ExaminerDashboard = {
  data() { return { s: null }; },
  template: `
  <div>
    <h4 class="mb-3">Examiner dashboard</h4>
    <div class="row g-3 mb-4" v-if="s">
      <div class="col-6 col-md-3" v-for="c in cards" :key="c[0]">
        <div class="card stat-card shadow-sm h-100"><div class="card-body">
          <div class="text-muted small">{{ c[0] }}</div><div class="display-6">{{ s[c[1]] }}</div></div></div>
      </div>
    </div>
    <h6>Assigned examinations</h6>
    <div class="table-responsive" v-if="s"><table class="table table-sm bg-white">
      <thead><tr><th>Examination</th><th>Type</th><th>Status</th><th>Slot creation window</th><th></th></tr></thead>
      <tbody>
        <tr v-for="e in s.exams" :key="e.id">
          <td><b>{{ e.name }}</b><div class="small text-muted">{{ e.course_code }}</div></td>
          <td>{{ e.exam_type }}</td><td><span :class="badge(e.status)">{{ e.status }}</span></td>
          <td class="small">{{ fdate(e.slot_create_start) }} to {{ fdate(e.slot_create_end) }}
            <span class="badge bg-success ms-1" v-if="e.slot_creation_active">open now</span></td>
          <td class="text-end"><router-link class="btn btn-outline-primary btn-sm" :to="{ path: '/examiner/slots', query: { exam: e.id } }">Slots</router-link></td>
        </tr>
        <tr v-if="!s.exams.length"><td colspan="5" class="text-center text-muted">No examinations assigned to you yet</td></tr>
      </tbody></table></div>
  </div>`,
  computed: {
    cards() { return [['Assigned examinations', 'assigned_exams'], ['My slots', 'slots'], ['Booked students', 'booked_students'], ['Pending evaluations', 'pending_evaluations']]; },
  },
  async mounted() { try { this.s = await api('/examiner/dashboard'); } catch (e) { toast(e.message, 'danger'); } },
};

const ExaminerSlots = {
  data() { return { exams: [], examId: '', slots: [], form: this.blank(), editing: null }; },
  computed: {
    exam() { return this.exams.find(e => e.id === this.examId); },
    canCreate() { return this.exam && this.exam.slot_creation_active; },
    today() { return new Date().toISOString().slice(0, 10); },
  },
  template: `
  <div>
    <h4 class="mb-3">My examination slots</h4>
    <div class="row g-2 mb-3">
      <div class="col-md-6"><select class="form-select" v-model="examId" @change="loadSlots">
        <option value="" disabled>Select an examination</option>
        <option v-for="e in exams" :key="e.id" :value="e.id">{{ e.name }} ({{ e.course_code }})</option></select></div>
      <div class="col-md-6 d-flex align-items-center" v-if="exam">
        <span :class="badge(exam.status)" class="me-2">{{ exam.status }}</span>
        <span class="small" :class="canCreate ? 'text-success' : 'text-danger'">
          {{ canCreate ? 'Slot creation is open' : 'Slot creation is closed or outside its dates' }}</span>
        <button class="btn btn-outline-dark btn-sm ms-auto" @click="complete" v-if="exam.status !== 'Completed'">Mark exam completed</button>
      </div>
    </div>
    <div class="card shadow-sm mb-3" v-if="exam && canCreate"><div class="card-body">
      <h6>{{ editing ? 'Edit slot' : 'New slot' }}</h6>
      <form class="row g-2" @submit.prevent="save">
        <div class="col-md-3"><label class="form-label">Date</label><input type="date" class="form-control" v-model="form.date" required :min="today"></div>
        <div class="col-6 col-md-2"><label class="form-label">Start</label><input type="time" class="form-control" v-model="form.start_time" required></div>
        <div class="col-6 col-md-2"><label class="form-label">End</label><input type="time" class="form-control" v-model="form.end_time" required></div>
        <div class="col-md-2"><label class="form-label">Capacity</label><input type="number" min="1" class="form-control" v-model.number="form.capacity" required></div>
        <div class="col-md-3"><label class="form-label">Meeting link (optional)</label><input class="form-control" v-model.trim="form.meeting_link"></div>
        <div class="col-12">
          <button class="btn btn-primary btn-sm me-2">{{ editing ? 'Update slot' : 'Create slot' }}</button>
          <button type="button" class="btn btn-light btn-sm" v-if="editing" @click="reset">Cancel edit</button></div>
      </form>
    </div></div>
    <div class="table-responsive"><table class="table table-sm bg-white">
      <thead><tr><th>Date</th><th>Time</th><th>Booked</th><th>Status</th><th>Link</th><th></th></tr></thead>
      <tbody>
        <tr v-for="s in slots" :key="s.id">
          <td>{{ s.date }}</td><td>{{ s.start_time }}-{{ s.end_time }}</td><td>{{ s.booked }}/{{ s.capacity }}</td>
          <td><span :class="badge(s.status)">{{ s.status }}</span></td>
          <td class="small">{{ s.meeting_link }}</td>
          <td class="text-end text-nowrap">
            <router-link class="btn btn-outline-success btn-sm me-1" :to="'/examiner/slots/' + s.id">Students</router-link>
            <button class="btn btn-outline-primary btn-sm me-1" @click="edit(s)">Edit</button>
            <button class="btn btn-outline-danger btn-sm" @click="remove(s)">Remove</button></td>
        </tr>
        <tr v-if="!slots.length"><td colspan="6" class="text-center text-muted">No slots yet</td></tr>
      </tbody></table></div>
  </div>`,
  async mounted() {
    try {
      this.exams = await api('/examiner/exams');
      const wanted = parseInt(this.$route.query.exam);
      this.examId = this.exams.find(e => e.id === wanted) ? wanted : (this.exams[0] ? this.exams[0].id : '');
      if (this.examId) this.loadSlots();
    } catch (e) { toast(e.message, 'danger'); }
  },
  methods: {
    blank() { return { date: '', start_time: '', end_time: '', capacity: 1, meeting_link: '' }; },
    reset() { this.form = this.blank(); this.editing = null; },
    async loadSlots() {
      this.reset();
      try { this.slots = await api('/examiner/slots?exam_id=' + this.examId); } catch (e) { toast(e.message, 'danger'); }
    },
    edit(s) { this.form = { date: s.date, start_time: s.start_time, end_time: s.end_time, capacity: s.capacity, meeting_link: s.meeting_link || '' }; this.editing = s.id; window.scrollTo(0, 0); },
    async save() {
      try {
        if (this.editing) await api('/examiner/slots/' + this.editing, 'PUT', this.form);
        else await api('/examiner/slots', 'POST', { ...this.form, exam_id: this.examId });
        toast('Slot saved'); this.loadSlots();
      } catch (e) { toast(e.message, 'danger'); }
    },
    async remove(s) {
      if (!confirm('Remove this slot?')) return;
      try { await api('/examiner/slots/' + s.id, 'DELETE'); toast('Slot removed'); this.loadSlots(); } catch (e) { toast(e.message, 'danger'); }
    },
    async complete() {
      if (!confirm('Mark this examination as completed?')) return;
      try { await api('/examiner/exams/' + this.examId + '/status', 'PUT', { status: 'Completed' }); toast('Marked completed'); this.exams = await api('/examiner/exams'); this.loadSlots(); }
      catch (e) { toast(e.message, 'danger'); }
    },
  },
};

const ExaminerSlotStudents = {
  data() { return { d: null, active: null, scores: {}, remarks: '' }; },
  template: `
  <div v-if="d">
    <router-link to="/examiner/slots" class="small">&larr; Back to slots</router-link>
    <h4 class="mb-1 mt-2">{{ d.slot.exam_name }}</h4>
    <p class="text-muted">{{ d.slot.date }} {{ d.slot.start_time }}-{{ d.slot.end_time }} - {{ d.slot.booked }}/{{ d.slot.capacity }} booked
      <a v-if="d.slot.meeting_link" :href="d.slot.meeting_link" target="_blank">Meeting link</a></p>

    <div class="card shadow-sm mb-3" v-if="active"><div class="card-body">
      <h6>Evaluate {{ active.student_name }} <span class="text-muted small">(max {{ d.max_marks }} marks overall)</span></h6>
      <div class="alert alert-warning py-2" v-if="!d.rubrics.length">The Admin has not added rubric criteria for this examination yet.</div>
      <form @submit.prevent="submit" v-else>
        <div class="row g-2 mb-2" v-for="r in d.rubrics" :key="r.id">
          <div class="col-md-6"><label class="form-label mb-0">{{ r.criterion_name }}</label>
            <div class="small text-muted">{{ r.description }} (weight {{ r.weightage }})</div></div>
          <div class="col-md-3"><div class="input-group input-group-sm">
            <input type="number" class="form-control" min="0" :max="r.max_marks" step="any" v-model.number="scores[r.id]" required>
            <span class="input-group-text">/ {{ r.max_marks }}</span></div></div>
        </div>
        <div class="mb-2"><label class="form-label">Remarks and feedback</label>
          <textarea class="form-control" rows="2" v-model="remarks" required></textarea></div>
        <button class="btn btn-primary btn-sm me-2">Submit evaluation</button>
        <button type="button" class="btn btn-light btn-sm" @click="active = null">Cancel</button>
      </form>
    </div></div>

    <div class="table-responsive"><table class="table table-sm bg-white">
      <thead><tr><th>Student</th><th>Email</th><th>Status</th><th>Marks</th><th></th></tr></thead>
      <tbody>
        <tr v-for="b in d.students" :key="b.id">
          <td>{{ b.student_name }}</td><td>{{ b.student_email }}</td>
          <td><span :class="badge(b.status)">{{ b.status }}</span></td>
          <td>{{ b.evaluation ? b.evaluation.total_marks + ' / ' + d.max_marks : '-' }}</td>
          <td class="text-end"><button class="btn btn-outline-primary btn-sm" @click="start(b)">{{ b.evaluation ? 'Edit evaluation' : 'Evaluate' }}</button></td>
        </tr>
        <tr v-if="!d.students.length"><td colspan="5" class="text-center text-muted">No students have booked this slot</td></tr>
      </tbody></table></div>
  </div>`,
  mounted() { this.load(); },
  methods: {
    async load() { try { this.d = await api('/examiner/slots/' + this.$route.params.id + '/students'); } catch (e) { toast(e.message, 'danger'); } },
    start(b) {
      this.active = b; this.scores = {}; this.remarks = b.evaluation ? b.evaluation.remarks : '';
      if (b.evaluation) b.evaluation.scores.forEach(s => { this.scores[s.rubric_id] = s.marks; });
      window.scrollTo(0, 0);
    },
    async submit() {
      const body = { remarks: this.remarks, scores: this.d.rubrics.map(r => ({ rubric_id: r.id, marks: this.scores[r.id] })) };
      try {
        const ev = await api('/examiner/bookings/' + this.active.id + '/evaluate', 'POST', body);
        toast('Evaluation saved. Total: ' + ev.total_marks + ' / ' + this.d.max_marks);
        this.active = null; this.load();
      } catch (e) { toast(e.message, 'danger'); }
    },
  },
};
