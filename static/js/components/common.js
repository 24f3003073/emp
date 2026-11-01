// Shared components: login, register, profile, navbar and toasts.

const ToastBox = {
  data() { return { store }; },
  template: `
  <div class="toast-box">
    <div v-for="t in store.toasts" :key="t.id" class="alert shadow-sm py-2 mb-2" :class="'alert-' + t.type">{{ t.message }}</div>
  </div>`,
};

const LoginPage = {
  data() { return { email: '', password: '', busy: false }; },
  template: `
  <div class="row justify-content-center mt-5"><div class="col-md-6 col-lg-4">
    <div class="card shadow-sm"><div class="card-body p-4">
      <h4 class="text-center mb-1">Examination Management Portal</h4>
      <p class="text-center text-muted small mb-4">Log in as Admin, Examiner or Student</p>
      <form @submit.prevent="submit">
        <div class="mb-3"><label class="form-label">Email</label>
          <input type="email" class="form-control" v-model.trim="email" required></div>
        <div class="mb-3"><label class="form-label">Password</label>
          <input type="password" class="form-control" v-model="password" required></div>
        <button class="btn btn-primary w-100" :disabled="busy">Log in</button>
      </form>
      <p class="mt-3 mb-0 text-center small">New student? <router-link to="/register">Create an account</router-link></p>
    </div></div>
  </div></div>`,
  methods: {
    async submit() {
      this.busy = true;
      try {
        const d = await api('/auth/login', 'POST', { email: this.email, password: this.password });
        setSession(d);
        this.$router.push(homeFor(d.role));
      } catch (e) { toast(e.message, 'danger'); } finally { this.busy = false; }
    },
  },
};

const RegisterPage = {
  data() { return { form: { name: '', email: '', phone: '', password: '' }, busy: false }; },
  template: `
  <div class="row justify-content-center mt-4"><div class="col-md-6 col-lg-5">
    <div class="card shadow-sm"><div class="card-body p-4">
      <h4 class="mb-3">Student registration</h4>
      <form @submit.prevent="submit">
        <div class="mb-3"><label class="form-label">Full name</label>
          <input class="form-control" v-model.trim="form.name" required minlength="2"></div>
        <div class="mb-3"><label class="form-label">Email</label>
          <input type="email" class="form-control" v-model.trim="form.email" required></div>
        <div class="mb-3"><label class="form-label">Phone (optional)</label>
          <input class="form-control" v-model.trim="form.phone" pattern="[0-9+ \\-]{7,15}" title="7 to 15 digits"></div>
        <div class="mb-3"><label class="form-label">Password (min 6 characters)</label>
          <input type="password" class="form-control" v-model="form.password" required minlength="6"></div>
        <button class="btn btn-primary w-100" :disabled="busy">Register</button>
      </form>
      <p class="mt-3 mb-0 text-center small">Already registered? <router-link to="/login">Log in</router-link></p>
    </div></div>
  </div></div>`,
  methods: {
    async submit() {
      this.busy = true;
      try {
        const d = await api('/auth/register', 'POST', this.form);
        toast(d.message);
        this.$router.push('/login');
      } catch (e) { toast(e.message, 'danger'); } finally { this.busy = false; }
    },
  },
};

const ProfilePage = {
  data() { return { p: null, password: '', store }; },
  template: `
  <div class="row justify-content-center"><div class="col-md-7 col-lg-5" v-if="p">
    <div class="card shadow-sm"><div class="card-body">
      <h4 class="mb-3">My profile <span class="badge bg-secondary text-capitalize fs-6">{{ p.role }}</span></h4>
      <form @submit.prevent="save">
        <div class="mb-3"><label class="form-label">Email</label>
          <input class="form-control" :value="p.email" disabled></div>
        <div class="mb-3"><label class="form-label">Name</label>
          <input class="form-control" v-model.trim="p.name" required minlength="2"></div>
        <div class="mb-3"><label class="form-label">Phone</label>
          <input class="form-control" v-model.trim="p.phone" pattern="[0-9+ \\-]{7,15}" title="7 to 15 digits"></div>
        <template v-if="p.role === 'examiner'">
          <div class="mb-3"><label class="form-label">Department</label>
            <input class="form-control" v-model.trim="p.department"></div>
          <div class="mb-3"><label class="form-label">Contact details</label>
            <input class="form-control" v-model.trim="p.contact_details"></div>
        </template>
        <div class="mb-3"><label class="form-label">New password (leave blank to keep)</label>
          <input type="password" class="form-control" v-model="password" minlength="6"></div>
        <button class="btn btn-primary">Save changes</button>
      </form>
    </div></div>
  </div></div>`,
  async mounted() {
    try { this.p = await api('/auth/profile'); } catch (e) { toast(e.message, 'danger'); }
  },
  methods: {
    async save() {
      const body = { name: this.p.name, phone: this.p.phone };
      if (this.password) body.password = this.password;
      if (this.p.role === 'examiner') { body.department = this.p.department; body.contact_details = this.p.contact_details; }
      try {
        this.p = await api('/auth/profile', 'PUT', body);
        store.name = this.p.name; localStorage.setItem('name', this.p.name);
        this.password = '';
        toast('Profile updated');
      } catch (e) { toast(e.message, 'danger'); }
    },
  },
};

const NavBar = {
  data() { return { store, timer: null }; },
  computed: {
    links() {
      if (store.role === 'admin') return [
        ['/admin', 'Dashboard'], ['/admin/courses', 'Courses'], ['/admin/exams', 'Exams'],
        ['/admin/examiners', 'Examiners'], ['/admin/students', 'Students'], ['/admin/slots', 'Slots'],
        ['/admin/bookings', 'Bookings'], ['/admin/search', 'Search']];
      if (store.role === 'examiner') return [['/examiner', 'Dashboard'], ['/examiner/slots', 'My slots']];
      return [['/student', 'Dashboard'], ['/student/exams', 'Examinations'],
              ['/student/bookings', 'My bookings'], ['/student/results', 'Results']];
    },
  },
  template: `
  <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
    <div class="container">
      <router-link class="navbar-brand" :to="links[0][0]">EMP</router-link>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#nav">
        <span class="navbar-toggler-icon"></span></button>
      <div class="collapse navbar-collapse" id="nav">
        <ul class="navbar-nav me-auto">
          <li class="nav-item" v-for="l in links" :key="l[0]">
            <router-link class="nav-link" :to="l[0]">{{ l[1] }}</router-link></li>
        </ul>
        <span class="navbar-text me-3 text-white">{{ store.name }}</span>
        <router-link class="btn btn-outline-light btn-sm me-2" to="/profile">Profile</router-link>
        <button class="btn btn-light btn-sm" @click="logout">Log out</button>
      </div>
    </div>
  </nav>`,
  mounted() { this.poll(); this.timer = setInterval(this.poll, 15000); },
  beforeUnmount() { clearInterval(this.timer); },
  methods: {
    async poll() {
      try {
        const list = await api('/notifications');
        const fresh = list.filter(n => !n.is_read);
        if (!fresh.length) return;
        fresh.slice(0, 3).reverse().forEach(n => toast(n.message, n.kind === 'warning' ? 'warning' : 'info'));
        await api('/notifications/read', 'POST');
      } catch (e) { /* ignore polling errors */ }
    },
    logout() { clearSession(); this.$router.push('/login'); },
  },
};
