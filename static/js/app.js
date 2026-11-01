// Router and root Vue app.
const routes = [
  { path: '/', redirect: () => (store.token ? homeFor(store.role) : '/login') },
  { path: '/login', component: LoginPage, meta: { public: true } },
  { path: '/register', component: RegisterPage, meta: { public: true } },
  { path: '/profile', component: ProfilePage },

  { path: '/admin', component: AdminDashboard, meta: { role: 'admin' } },
  { path: '/admin/courses', component: AdminCourses, meta: { role: 'admin' } },
  { path: '/admin/exams', component: AdminExams, meta: { role: 'admin' } },
  { path: '/admin/examiners', component: AdminExaminers, meta: { role: 'admin' } },
  { path: '/admin/students', component: AdminStudents, meta: { role: 'admin' } },
  { path: '/admin/slots', component: AdminSlots, meta: { role: 'admin' } },
  { path: '/admin/bookings', component: AdminBookings, meta: { role: 'admin' } },
  { path: '/admin/search', component: AdminSearch, meta: { role: 'admin' } },

  { path: '/examiner', component: ExaminerDashboard, meta: { role: 'examiner' } },
  { path: '/examiner/slots', component: ExaminerSlots, meta: { role: 'examiner' } },
  { path: '/examiner/slots/:id', component: ExaminerSlotStudents, meta: { role: 'examiner' } },

  { path: '/student', component: StudentDashboard, meta: { role: 'student' } },
  { path: '/student/exams', component: StudentExams, meta: { role: 'student' } },
  { path: '/student/bookings', component: StudentBookings, meta: { role: 'student' } },
  { path: '/student/results', component: StudentResults, meta: { role: 'student' } },

  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = VueRouter.createRouter({ history: VueRouter.createWebHashHistory(), routes });

router.beforeEach((to) => {
  if (to.meta.public) return store.token ? homeFor(store.role) : true;
  if (!store.token) return '/login';
  if (to.meta.role && to.meta.role !== store.role) return homeFor(store.role);
  return true;
});

const App = {
  components: { NavBar, ToastBox },
  setup() { return { store }; },
  template: `
    <div>
      <nav-bar v-if="store.token" :key="store.token"></nav-bar>
      <div class="container py-4"><router-view :key="$route.fullPath"></router-view></div>
      <toast-box></toast-box>
    </div>`,
};

const app = Vue.createApp(App);
app.config.globalProperties.badge = badge;
app.config.globalProperties.fdate = fdate;
app.use(router);
app.mount('#app');
